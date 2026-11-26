"""Opt-in public HTTPS acceptance; never reads or changes an existing library."""
import datetime,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from library import Library

URL='https://blog.python.org/feeds/posts/default?alt=rss'
def main():
 with tempfile.TemporaryDirectory(prefix='feed-grove-live-') as tmp:
  path=tmp+'/library.sqlite3';lib=Library(path)
  try:
   first=lib.refresh(URL)
   entries=lib.entries()
   assert first>0 and entries, 'Public feed did not contain entries'
   entry=entries[0];key=entry['key'];lib.mark(URL,key,read=True,starred=True)
   second=lib.refresh(URL)
   assert second>0, 'Second refresh was empty'
   matches=[e for e in lib.entries() if e['feed_url']==URL and e['key']==key]
   assert len(matches)==1, 'Refresh duplicated an existing entry'
   assert matches[0]['is_read'] and matches[0]['starred'], 'Refresh lost reading state'
   assert URL.encode() in lib.export_opml(), 'Subscription missing from OPML'
  finally:lib.close()
  lib=Library(path)
  try:
   saved=[e for e in lib.entries() if e['feed_url']==URL and e['key']==key]
   assert saved[0]['is_read'] and saved[0]['starred'], 'Reading state did not persist after reopening'
  finally:lib.close()
 return {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':URL,'first_refresh_entries':first,'second_refresh_entries':second,'passed':['Direct DNS and verified HTTPS','Live RSS ingestion twice','No duplicate stored entry','Read/star state survives refresh and reopen','OPML retains subscription'],'limits':['One public feed only','No Feedly account export or hardware/browser acceptance implied']}
if __name__=='__main__':print(json.dumps(main(),indent=2))
