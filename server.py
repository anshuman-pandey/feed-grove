"""Single-user loopback reader. Do not expose this server publicly."""
import argparse
import json
import secrets
import sqlite3
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from feeds import FeedError, MAX_BYTES, parse_opml
from library import Library

STATIC = Path(__file__).parent / 'web'


def make_server(db_path, port=5142):
    token = secrets.token_urlsafe(32)
    # Initialize schema before concurrent requests.
    Library(db_path).close()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, code, body, kind='application/json'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host') == expected and self.headers.get('Origin', 'http://' + expected) == 'http://' + expected

        def do_GET(self):
            if not self.trusted():
                return self.respond(403, {'error':'Open the app using its exact loopback address.'})
            assets = {'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css'),'/locales.js':('locales.js','text/javascript')}
            if self.path in assets:
                name, kind = assets[self.path]
                return self.respond(200, (STATIC/name).read_bytes(), kind)
            if self.path == '/api/library':
                lib = Library(db_path)
                try:
                    return self.respond(200, {'token':token,'feeds':[asdict(s) for s in lib.subscriptions()],'entries':lib.entries()})
                finally:
                    lib.close()
            if self.path == '/api/opml':
                lib = Library(db_path)
                try:
                    return self.respond(200, lib.export_opml(), 'application/xml')
                finally:
                    lib.close()
            return self.respond(404, {'error':'Not found.'})

        def do_POST(self):
            if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Feed-Grove',''),token):
                return self.respond(403, {'error':'Reload the reader before changing the library.'})
            lib = None
            try:
                if self.headers.get('Content-Type') != 'application/json':
                    raise FeedError('Expected a JSON request.')
                length = int(self.headers.get('Content-Length','0'))
                if length <= 0 or length > MAX_BYTES * 6 + 8192:
                    raise FeedError('Request is too large or empty.')
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise FeedError('Expected an object.')
                lib = Library(db_path)
                if self.path in ('/api/preview','/api/import','/api/ingest'):
                    if not isinstance(data.get('xml'),str):
                        raise FeedError('Select an XML file first.')
                    raw=data['xml'].encode('utf-8')
                    if self.path == '/api/preview':
                        existing={s.url for s in lib.subscriptions()}
                        return self.respond(200, {'feeds':[dict(asdict(s),exists=s.url in existing) for s in parse_opml(raw)]})
                    count=lib.import_opml(raw) if self.path == '/api/import' else lib.ingest(data['url'],raw)
                    return self.respond(200, {'processed':count})
                if self.path == '/api/refresh':
                    return self.respond(200, {'processed':lib.refresh(data['url'])})
                if self.path == '/api/mark':
                    lib.mark(data['url'],data['key'],read=data.get('read'),starred=data.get('starred'))
                    return self.respond(200, {'updated':True})
                return self.respond(404, {'error':'Not found.'})
            except (FeedError,ValueError,KeyError,TypeError,AttributeError,UnicodeError) as e:
                return self.respond(400, {'error':str(e) if isinstance(e,FeedError) else 'Invalid request fields.'})
            except (OSError,sqlite3.Error):
                return self.respond(503, {'error':'Library or connection unavailable. Retry without deleting your database.'})
            finally:
                if lib is not None:
                    lib.close()

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='feed-grove.sqlite3')
    parser.add_argument('--port',type=int,default=5142)
    args=parser.parse_args()
    server=make_server(args.db,args.port)
    print(f'Feed Grove: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
