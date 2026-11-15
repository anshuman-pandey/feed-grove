import os,subprocess,tempfile,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import make_server
with tempfile.TemporaryDirectory() as folder:
 server=make_server(folder+'/library.sqlite3',0)
 thread=threading.Thread(target=server.serve_forever);thread.start()
 try:
  subprocess.run(['node','browser.test.cjs'],check=True,env={**os.environ,'BASE_URL':f'http://127.0.0.1:{server.server_port}'})
 finally:
  server.shutdown();server.server_close();thread.join()
