import http.client,json,tempfile,threading,unittest
from server import make_server
class ServerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=make_server(self.temp.name+'/db',0);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def request(self,path,body=None,headers=None):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request('GET' if body is None else 'POST',path,body,headers or {});r=c.getresponse();result=(r.status,r.read());c.close();return result
 def test_host_and_csrf(self):
  self.assertEqual(self.request('/api/library',headers={'Host':'evil.example'})[0],403)
  self.assertEqual(self.request('/api/import','{}',{'Content-Type':'application/json'})[0],403)
 def test_preview_is_read_only_and_import_is_authenticated(self):
  token=json.loads(self.request('/api/library')[1])['token'];h={'Content-Type':'application/json','X-Feed-Grove':token}
  body=json.dumps({'xml':'<opml><body><outline text="Notes" xmlUrl="https://example.com/feed"/></body></opml>'})
  self.assertEqual(self.request('/api/preview',body,h)[0],200)
  self.assertEqual(json.loads(self.request('/api/library')[1])['feeds'],[])
  self.assertEqual(self.request('/api/import',body,h)[0],200)
  self.assertEqual(len(json.loads(self.request('/api/library')[1])['feeds']),1)
  h['Origin']='https://evil.example';self.assertEqual(self.request('/api/import',body,h)[0],403)
 def test_source_and_database_not_served(self):
  for path in ['/../server.py','/feed-grove.sqlite3','/server.py']:self.assertEqual(self.request(path)[0],404)
