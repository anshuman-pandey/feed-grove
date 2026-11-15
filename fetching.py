"""Public feed retrieval: pinned addresses, verified TLS, no ambient proxies."""
import http.client
import ipaddress
import json
import socket
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urljoin
from feeds import FeedError, MAX_BYTES, http_url

DNS_SCRIPT = '''import json,socket,sys
print(json.dumps(sorted(set(x[4][0] for x in socket.getaddrinfo(sys.argv[1],None,type=socket.SOCK_STREAM)))))'''


def public_addresses(host, timeout):
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            output = subprocess.run([sys.executable, '-c', DNS_SCRIPT, host],
                                    capture_output=True, text=True, timeout=timeout, check=True)
            addresses = json.loads(output.stdout)
        except (subprocess.SubprocessError, ValueError, OSError):
            raise FeedError('Feed hostname could not be resolved in time.') from None
    if not addresses:
        raise FeedError('Feed hostname has no addresses.')
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, 'ipv4_mapped', None):
            raise FeedError('Feed URLs must resolve only to public Internet addresses.')
    return addresses


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout, secure):
        super().__init__(host, port, timeout=timeout)
        self.address = address
        self.secure = secure

    def connect(self):
        # Connect directly to the checked numeric address; never re-resolve host.
        family = socket.AF_INET6 if ':' in self.address else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        self.sock = sock
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.address, self.port))
            if self.secure:
                self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def fetch_feed(url, timeout=20):
    """Return (XML bytes, final URL). A deadline covers DNS, redirects and body."""
    if timeout <= 0 or timeout > 60:
        raise FeedError('Refresh timeout must be between 0 and 60 seconds.')
    deadline = time.monotonic() + timeout
    current = http_url(url)
    for hop in range(5):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FeedError('Feed refresh timed out.')
        parts = urlsplit(current)
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        if port not in (80, 443):
            raise FeedError('Public feeds must use port 80 or 443.')
        addresses = public_addresses(parts.hostname, min(5, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FeedError('Feed refresh timed out.')
        conn = PinnedHTTP(parts.hostname, port, addresses[0], remaining, parts.scheme == 'https')
        response = None
        transport = None
        expired = threading.Event()

        def abort():
            expired.set()
            active_socket = conn.sock or transport
            if active_socket is not None:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                active_socket.close()

        timer = threading.Timer(remaining, abort)
        timer.daemon = True
        timer.start()
        try:
            path = parts.path or '/'
            if parts.query:
                path += '?' + parts.query
            conn.request('GET', path, headers={'User-Agent':'FeedGrove/0.1',
                         'Accept':'application/atom+xml, application/rss+xml, application/xml, text/xml',
                         'Accept-Encoding':'identity','Connection':'close'})
            transport = conn.sock
            response = conn.getresponse()
            if response.status in (301,302,303,307,308):
                location = response.getheader('Location')
                if not location:
                    raise FeedError('Feed redirect has no destination.')
                following = http_url(urljoin(current, location))
                if parts.scheme == 'https' and urlsplit(following).scheme != 'https':
                    raise FeedError('Refusing an HTTPS-to-HTTP feed redirect.')
                current = following
                continue
            if response.status != 200:
                raise FeedError(f'Feed server returned HTTP {response.status}.')
            if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise FeedError('Compressed feed responses are not supported.')
            length = response.getheader('Content-Length')
            if length is not None:
                if not length.isdecimal() or int(length) > MAX_BYTES:
                    raise FeedError('Feed response exceeds 2 MiB or has invalid length.')
            body = bytearray()
            while True:
                chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                if expired.is_set() or time.monotonic() >= deadline:
                    raise FeedError('Feed refresh timed out.')
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise FeedError('Feed response exceeds 2 MiB.')
            if length is not None and len(body) != int(length):
                raise FeedError('Feed response ended before its declared length.')
            return bytes(body), current
        except (OSError, http.client.HTTPException, UnicodeError, ValueError) as e:
            if isinstance(e, FeedError):
                raise
            raise FeedError('Feed refresh timed out.' if expired.is_set() else
                            'Feed connection failed; check its URL and TLS certificate.') from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            conn.close()
    raise FeedError('Feed exceeded four redirects.')
