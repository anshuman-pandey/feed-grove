"""SQLite transactions preserve reading state while feed entries change."""
import json
import sqlite3
from feeds import Subscription, parse_opml, export_opml, parse_feed, http_url, FeedError


class Library:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys = ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS feeds (
                url TEXT PRIMARY KEY, title TEXT NOT NULL, folder TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entries (
                feed_url TEXT NOT NULL REFERENCES feeds(url) ON DELETE CASCADE,
                key TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
                summary TEXT NOT NULL, published TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                starred INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(feed_url, key));
        ''')

    def close(self):
        self.db.close()

    def subscriptions(self):
        return [Subscription(r['url'], r['title'], tuple(json.loads(r['folder'])))
                for r in self.db.execute('SELECT * FROM feeds ORDER BY rowid')]

    def import_opml(self, raw):
        incoming = parse_opml(raw)  # All validation occurs before writing anything.
        before = self.db.total_changes
        with self.db:
            for sub in incoming:
                self.db.execute('INSERT OR IGNORE INTO feeds VALUES (?, ?, ?)',
                                (sub.url, sub.title, json.dumps(sub.folder)))
        return self.db.total_changes - before

    def export_opml(self):
        return export_opml(self.subscriptions())

    def ingest(self, feed_url, raw, *, document_url=None):
        feed_url = http_url(feed_url)
        title, entries = parse_feed(raw, document_url or feed_url)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO feeds VALUES (?, ?, ?)', (feed_url, title, '[]'))
            for e in entries:
                self.db.execute('''INSERT INTO entries
                    (feed_url,key,title,url,summary,published) VALUES (?,?,?,?,?,?)
                    ON CONFLICT(feed_url,key) DO UPDATE SET
                    title=excluded.title,url=excluded.url,summary=excluded.summary,published=excluded.published''',
                    (feed_url,e.key,e.title,e.url,e.summary,e.published))
        return len(entries)

    def refresh(self, feed_url):
        from fetching import fetch_feed
        raw, final_url = fetch_feed(feed_url)
        return self.ingest(feed_url, raw, document_url=final_url)

    def entries(self, query='', unread=False, starred=False, feed_url=None):
        clauses, params = [], []
        if unread:
            clauses.append('is_read=0')
        if starred:
            clauses.append('starred=1')
        if feed_url is not None:
            clauses.append('feed_url=?')
            params.append(http_url(feed_url))
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        rows = self.db.execute('SELECT * FROM entries' + where + ' ORDER BY rowid DESC', params)
        # Literal, Unicode casefold search: '%' and '_' are ordinary characters.
        needle = query.casefold()
        return [dict(r) for r in rows if needle in (r['title'] + '\n' + r['summary']).casefold()]

    def mark(self, feed_url, key, *, read=None, starred=None):
        values = {'is_read': read, 'starred': starred}
        selected = {k: v for k, v in values.items() if v is not None}
        if not selected or any(type(v) is not bool for v in selected.values()):
            raise FeedError('Specify a boolean read or starred value.')
        with self.db:
            result = self.db.execute('UPDATE entries SET ' + ','.join(k+'=?' for k in selected)
                                    + ' WHERE feed_url=? AND key=?',
                                    [int(v) for v in selected.values()] + [http_url(feed_url), key])
            if not result.rowcount:
                raise FeedError('Entry not found.')
