import tempfile
import unittest
from pathlib import Path
from feeds import *
from library import Library

RSS = b'''<rss version="2.0"><channel><title>Field notes</title><item>
<guid>stable-1</guid><title>A &amp; B</title><link>/story</link>
<description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;</description>
</item></channel></rss>'''
OPML = b'''<opml version="2.0"><body><outline text="Science &amp; nature"><outline text="Space">
<outline text="Field notes" xmlUrl="https://EXAMPLE.com:443/feed#top"/>
</outline></outline><outline text="Duplicate" xmlUrl="https://example.com/feed"/></body></opml>'''


class Parsing(unittest.TestCase):
    def test_folder_dedup_and_roundtrip(self):
        subscriptions = parse_opml(OPML)
        self.assertEqual(subscriptions,[Subscription('https://example.com/feed','Field notes',('Science & nature','Space'))])
        self.assertEqual(parse_opml(export_opml(subscriptions)),subscriptions)

    def test_rss_html_is_inert_and_relative_links_resolve(self):
        title, entries = parse_feed(RSS,'https://example.com/feed')
        self.assertEqual(title,'Field notes')
        self.assertEqual(entries[0].summary,'Hello world')
        self.assertEqual(entries[0].url,'https://example.com/story')
        self.assertEqual(entries[0].title,'A & B')

    def test_atom_namespace_base_and_text_semantics(self):
        raw = b'''<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://example.com/articles/">
        <title>Notes</title><entry xml:base="archive/"><id>urn:item:1</id>
        <title type="text">Literal &lt;b&gt;text&lt;/b&gt;</title>
        <content type="html">&lt;p&gt;Safe text&lt;/p&gt;</content>
        <link rel="self" href="api"/><link href="one"/></entry></feed>'''
        entry = parse_feed(raw,'https://example.com/feed')[1][0]
        self.assertEqual(entry.url,'https://example.com/articles/archive/one')
        self.assertEqual(entry.title,'Literal <b>text</b>')
        self.assertEqual(entry.summary,'Safe text')

    def test_unsafe_article_link_is_removed(self):
        self.assertEqual(parse_feed(RSS.replace(b'/story',b'javascript:alert(1)'), 'https://example.com/feed')[1][0].url,'')

    def test_unsafe_subscription_fails_entire_import(self):
        with self.assertRaises(FeedError):
            parse_opml(OPML.replace(b'https://example.com/feed',b'file:///etc/passwd'))

    def test_entities_dtd_and_utf16_are_rejected(self):
        for xml in ['<!DOCTYPE rss [<!ENTITY x "hello">]><rss/>',
                    '<!DOCTYPE rss SYSTEM "file:///etc/passwd"><rss/>']:
            for encoding in ('utf-8','utf-16'):
                with self.subTest(encoding=encoding,xml=xml),self.assertRaises(FeedError):
                    document(xml.encode(encoding))

    def test_limits_and_wrong_formats(self):
        for raw in [b'x'*(MAX_BYTES+1),b'<rss>',b'<html/>',b'<x>'*35+b'</x>'*35]:
            with self.assertRaises(FeedError):parse_feed(raw,'https://example.com/feed')

    def test_url_credentials_and_bad_ports(self):
        for url in ['https://user:secret@example.com/feed','https://example.com:99999/','file:///x','https://ex\nample.com']:
            with self.assertRaises(FeedError):http_url(url)

    def test_duplicate_guid_collapses_within_feed(self):
        item=RSS[RSS.index(b'<item>'):RSS.index(b'</item>')+7]
        self.assertEqual(len(parse_feed(RSS.replace(item,item+item),'https://example.com/feed')[1]),1)


class Persistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'library.sqlite3'
        self.lib = Library(self.path)

    def tearDown(self):
        self.lib.close(); self.temp.cleanup()

    def test_refresh_preserves_read_star_and_updates_content(self):
        self.lib.ingest('https://example.com/feed',RSS)
        entry = self.lib.entries()[0]
        self.lib.mark(entry['feed_url'],entry['key'],read=True,starred=True)
        self.lib.ingest(entry['feed_url'],RSS.replace(b'A &amp; B',b'Changed'))
        self.lib.close(); self.lib=Library(self.path)
        self.assertEqual(len(self.lib.entries()),1)
        self.assertEqual(self.lib.entries(starred=True)[0]['title'],'Changed')
        self.assertEqual(self.lib.entries(unread=True),[])

    def test_same_guid_in_two_feeds_is_distinct(self):
        for url in ['https://example.com/one','https://example.com/two']:self.lib.ingest(url,RSS)
        self.assertEqual(len(self.lib.entries()),2)

    def test_invalid_import_does_not_partially_write(self):
        raw=OPML.replace(b'</body>',b'<outline xmlUrl="javascript:bad"/></body>')
        with self.assertRaises(FeedError):self.lib.import_opml(raw)
        self.assertEqual(self.lib.subscriptions(),[])

    def test_reimport_does_not_overwrite_folders(self):
        self.assertEqual(self.lib.import_opml(OPML),1)
        self.assertEqual(self.lib.import_opml(OPML.replace(b'Space',b'Changed')),0)
        self.assertEqual(self.lib.subscriptions()[0].folder,('Science & nature','Space'))

    def test_literal_filter_and_read_reversal(self):
        self.lib.ingest('https://example.com/feed',RSS)
        self.assertEqual(len(self.lib.entries(query='WORLD')),1)
        self.assertEqual(self.lib.entries(query='%'),[])
        e=self.lib.entries()[0]
        self.lib.mark(e['feed_url'],e['key'],read=True)
        self.lib.mark(e['feed_url'],e['key'],read=False)
        self.assertEqual(len(self.lib.entries(unread=True)),1)

    def test_missing_entry_and_invalid_state_are_errors(self):
        for kwargs in ({'read':True},{'starred':'yes'},{}):
            with self.assertRaises(FeedError):self.lib.mark('https://example.com/feed','absent',**kwargs)


if __name__=='__main__': unittest.main()
