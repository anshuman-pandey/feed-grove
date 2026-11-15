import io
import socket
import ssl
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock
from fetching import fetch_feed, public_addresses, PinnedHTTP
from feeds import FeedError, MAX_BYTES
from library import Library


class Response:
    def __init__(self, body=b'<rss/>', status=200, headers=None):
        self.body=io.BytesIO(body)
        self.status=status
        self.headers=headers or {}
        self.closed=False
    def getheader(self,key,default=None):return self.headers.get(key,default)
    def read1(self,size):return self.body.read(size)
    def close(self):self.closed=True


class FetchTests(unittest.TestCase):
    def run_fetch(self,responses,url='https://example.com/feed'):
        conns=[]
        for response in responses:
            conn=Mock();conn.getresponse.return_value=response;conns.append(conn)
        with patch('fetching.public_addresses',return_value=['93.184.216.34']) as dns,patch('fetching.PinnedHTTP',side_effect=conns) as factory:
            result=fetch_feed(url)
        return result,conns,dns,factory

    def test_public_fetch_and_headers(self):
        response=Response(b'xml',headers={'Content-Length':'3'})
        result,conns,dns,factory=self.run_fetch([response])
        self.assertEqual(result,(b'xml','https://example.com/feed'))
        self.assertEqual(factory.call_args.args[2],'93.184.216.34')
        self.assertEqual(conns[0].request.call_args.kwargs['headers']['Accept-Encoding'],'identity')
        self.assertTrue(response.closed)

    def test_redirect_resolves_again_and_preserves_final_base(self):
        result,conns,dns,_=self.run_fetch([Response(status=302,headers={'Location':'https://other.example/nested/feed'}),Response()])
        self.assertEqual(result[1],'https://other.example/nested/feed')
        self.assertEqual([x.args[0] for x in dns.call_args_list],['example.com','other.example'])

    def test_redirect_to_private_address_is_blocked_before_connect(self):
        conn=Mock();conn.getresponse.return_value=Response(status=302,headers={'Location':'https://127.0.0.1/secret'})
        original=public_addresses
        def resolve(host,timeout):return ['93.184.216.34'] if host=='example.com' else original(host,timeout)
        with patch('fetching.public_addresses',side_effect=resolve),patch('fetching.PinnedHTTP',return_value=conn) as factory:
            with self.assertRaises(FeedError):fetch_feed('https://example.com/feed')
            self.assertEqual(factory.call_count,1)

    def test_private_reserved_mapped_multicast_addresses_rejected(self):
        for address in ['127.0.0.1','10.1.1.1','169.254.169.254','0.0.0.0','::1','fc00::1','::ffff:8.8.8.8','224.0.0.1','2001:db8::1']:
            with self.subTest(address=address),self.assertRaises(FeedError):public_addresses(address,1)

    def test_mixed_dns_answers_are_rejected(self):
        with patch('fetching.subprocess.run',return_value=Mock(stdout='["8.8.8.8","10.0.0.1"]')):
            with self.assertRaises(FeedError):public_addresses('example.com',1)

    def test_dns_timeout_is_coherent_error(self):
        with patch('fetching.subprocess.run',side_effect=subprocess.TimeoutExpired('dns',1)):
            with self.assertRaisesRegex(FeedError,'resolved in time'):public_addresses('example.com',1)

    def test_status_compression_length_and_truncated_body(self):
        for response in [Response(status=403),Response(headers={'Content-Encoding':'gzip'}),
                         Response(headers={'Content-Length':str(MAX_BYTES+1)}),
                         Response(headers={'Content-Length':'-1'}),Response(b'x',headers={'Content-Length':'2'}),
                         Response(b'x'*(MAX_BYTES+1))]:
            with self.subTest(headers=response.headers),self.assertRaises(FeedError):self.run_fetch([response])

    def test_bad_redirects(self):
        for location in ['http://example.com/feed','file:///etc/passwd','https://user:secret@example.com/']:
            with self.subTest(location=location),self.assertRaises(FeedError):self.run_fetch([Response(status=302,headers={'Location':location})])
        with self.assertRaisesRegex(FeedError,'four redirects'):
            self.run_fetch([Response(status=302,headers={'Location':'/loop'}) for _ in range(5)])

    def test_nonstandard_ports_rejected_before_dns(self):
        with patch('fetching.public_addresses') as dns:
            with self.assertRaises(FeedError):fetch_feed('https://example.com:8080/')
            dns.assert_not_called()

    def test_socket_uses_pinned_numeric_address_and_tls_hostname(self):
        raw=Mock();context=Mock()
        with patch('fetching.socket.socket',return_value=raw),patch('fetching.ssl.create_default_context',return_value=context):
            conn=PinnedHTTP('example.com',443,'93.184.216.34',2,True)
            conn.connect()
            raw.connect.assert_called_once_with(('93.184.216.34',443))
            context.wrap_socket.assert_called_once_with(raw,server_hostname='example.com')

    def test_tls_failure_does_not_retry_without_tls(self):
        conn=Mock();conn.request.side_effect=ssl.SSLError('bad certificate')
        with patch('fetching.public_addresses',return_value=['8.8.8.8']),patch('fetching.PinnedHTTP',return_value=conn):
            with self.assertRaisesRegex(FeedError,'TLS'):fetch_feed('https://example.com/feed')
            self.assertEqual(conn.request.call_count,1)

    def test_deadline_interrupts_detached_response_socket(self):
        conn=Mock();transport=Mock();conn.sock=transport
        response=Response();conn.getresponse.return_value=response
        def read(size):
            conn.sock=None # HTTPConnection detaches on Connection: close.
            timer.callback()
            return b''
        response.read1=read
        timer=Mock()
        def new_timer(delay,callback):timer.callback=callback;return timer
        with patch('fetching.public_addresses',return_value=['8.8.8.8']),patch('fetching.PinnedHTTP',return_value=conn),patch('fetching.threading.Timer',side_effect=new_timer):
            with self.assertRaisesRegex(FeedError,'timed out'):fetch_feed('https://example.com/feed')
            transport.shutdown.assert_called_once_with(socket.SHUT_RDWR)

    def test_refresh_uses_redirect_base_without_changing_subscription_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            lib=Library(folder+'/db')
            xml=b'<rss><channel><item><guid>x</guid><link>story</link></item></channel></rss>'
            with patch('fetching.fetch_feed',return_value=(xml,'https://cdn.example/path/feed')):
                self.assertEqual(lib.refresh('https://example.com/feed'),1)
            entry=lib.entries()[0]
            self.assertEqual(entry['feed_url'],'https://example.com/feed')
            self.assertEqual(entry['url'],'https://cdn.example/path/story')
            with patch('fetching.fetch_feed',return_value=(b'<html/>','https://example.com/feed')):
                with self.assertRaises(FeedError):lib.refresh('https://example.com/feed')
            self.assertEqual(len(lib.entries()),1)
            lib.close()
