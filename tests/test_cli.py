import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CommandWorkflow(unittest.TestCase):
    def test_migrate_ingest_star_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            opml = base/'subscriptions.opml'
            feed = base/'feed.xml'
            opml.write_text('<opml><body><outline text="Journal" xmlUrl="https://example.com/feed"/></body></opml>')
            feed.write_text('<rss><channel><title>Journal</title><item><guid>one</guid><title>First note</title></item></channel></rss>')

            def run(*args, success=True):
                result = subprocess.run([sys.executable,str(ROOT/'cli.py'),'--db',str(base/'library.sqlite3'),*args],capture_output=True,text=True)
                self.assertEqual(result.returncode,0 if success else 1,result.stderr)
                return result.stdout

            self.assertEqual(json.loads(run('import-opml',str(opml)))['processed'],1)
            run('ingest','https://example.com/feed',str(feed))
            entry=json.loads(run('list','--unread'))[0]
            run('mark',entry['feed_url'],entry['key'],'--read','yes','--starred','yes')
            run('ingest','https://example.com/feed',str(feed))
            self.assertEqual(json.loads(run('list','--unread')),[])
            self.assertEqual(len(json.loads(run('list','--starred'))),1)
            self.assertIn('https://example.com/feed',run('export-opml'))
            feed.write_text('<html/>')
            run('ingest','https://example.com/feed',str(feed),success=False)
            self.assertEqual(len(json.loads(run('list'))),1)

    def test_missing_database_directory_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'missing'/'library.sqlite3'
            result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--db',str(db),'list'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertIn('Check the database path',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertFalse(db.exists())

    def test_corrupt_database_error_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/'library.sqlite3';original=b'not a sqlite database\n'*20;db.write_bytes(original)
            result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--db',str(db),'list'],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertIn('keep your existing database',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
            self.assertEqual(db.read_bytes(),original)
