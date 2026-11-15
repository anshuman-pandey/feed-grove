# Feed Grove · development checkout

An open-source Feedly alternative in preparation. **Not launch-ready or published.**
The working component currently covers local RSS 2.0 / Atom 1.0 ingestion, OPML subscription migration, literal text filters, and persistent read/starred state. It does not fetch feeds or provide a browser interface yet.

## Try the ingestion tools

Requires Python 3.10+ and the pinned dependency in `requirements.txt`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python cli.py --db reading.sqlite3 import-opml subscriptions.opml
.venv/bin/python cli.py --db reading.sqlite3 ingest https://example.com/feed feed.xml
.venv/bin/python cli.py --db reading.sqlite3 list --unread
.venv/bin/python cli.py --db reading.sqlite3 export-opml > subscriptions-backup.opml
```

Supply your own exported OPML and downloaded feed XML. `ingest` does not make a network request. Run `mark URL KEY --read yes --starred yes` using the URL and key from `list`. `list --query word` searches titles and summaries; `--starred` filters saved entries. Reimporting a subscription leaves its existing folder intact. OPML exports subscriptions and folders, **not article content or reading state**; stop writers and back up the SQLite file for those.

Inputs are capped at 2 MiB, 2,000 entries per feed, and 500 unique subscriptions per OPML import. DTDs/entities, credentials in URLs, and unsupported document types are rejected. Feed HTML becomes inert plain text, unsafe article links are removed, and parameterized SQLite writes preserve flags during updates. No feed images, scripts, or external assets are loaded. RSS 1.0/RDF, enclosure downloads, full-article extraction, and date normalization are not implemented.

## What remains before launch

1. Bounded public HTTP(S) refresh, including redirect and DNS/private-address handling, timeouts, and clear per-feed errors.
2. A polished responsive reader, subscription/import preview, search, unread/starred filters, and six UI languages (en/de/es/ja/zh-CN/zh-TW).
3. End-to-end browser checks, real screenshots, visual README, install package and extracted-package acceptance.
4. Owner review and separate publication approval. No public repository, release, or demo is claimed.

Read [scope and distribution](docs/SCOPE.md) for the intended workflow and primary-source comparison. MIT licensed.
