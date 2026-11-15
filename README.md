# Feed Grove · development checkout

An open-source Feedly alternative in preparation. **Not launch-ready or published.**
The working component currently covers local RSS 2.0 / Atom 1.0 ingestion, OPML subscription migration, literal text filters, and persistent read/starred state. The CLI can refresh public feeds; the browser interface is not implemented yet.

## Try the ingestion tools

Requires Python 3.10+ and the pinned dependency in `requirements.txt`.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python cli.py --db reading.sqlite3 import-opml subscriptions.opml
.venv/bin/python cli.py --db reading.sqlite3 ingest https://example.com/feed feed.xml
.venv/bin/python cli.py --db reading.sqlite3 refresh https://example.com/feed
.venv/bin/python cli.py --db reading.sqlite3 list --unread
.venv/bin/python cli.py --db reading.sqlite3 export-opml > subscriptions-backup.opml
```

Supply your own exported OPML and downloaded feed XML. `ingest` does not make a network request. Run `mark URL KEY --read yes --starred yes` using the URL and key from `list`. `list --query word` searches titles and summaries; `--starred` filters saved entries. Reimporting a subscription leaves its existing folder intact. OPML exports subscriptions and folders, **not article content or reading state**; stop writers and back up the SQLite file for those.

Inputs are capped at 2 MiB, 2,000 entries per feed, and 500 unique subscriptions per OPML import. DTDs/entities, credentials in URLs, and unsupported document types are rejected. Feed HTML becomes inert plain text, unsafe article links are removed, and parameterized SQLite writes preserve flags during updates. No feed images, scripts, or external assets are loaded. RSS 1.0/RDF, enclosure downloads, full-article extraction, and date normalization are not implemented.

`refresh URL` downloads and ingests one public feed atomically. It allows ports 80/443, rejects non-public DNS answers and HTTPS downgrades, pins the checked connection address, verifies TLS, follows at most four redirects and caps the response at 2 MiB with a 20-second deadline (DNS gets at most five seconds per hop). Compressed responses are rejected; proxies, cookies and credentials are not used. A failed fetch or parse leaves stored entries unchanged. Use `ingest` with a local XML file if a feed requires unsupported transport.

## What remains before launch

1. Validate public HTTP(S) refresh outside this workspace: direct DNS failed here. Automated address/redirect/TLS/size/deadline tests pass; this is not live-network acceptance.
2. A polished responsive reader, subscription/import preview, search, unread/starred filters, and six UI languages (en/de/es/ja/zh-CN/zh-TW).
3. End-to-end browser checks, real screenshots, visual README, install package and extracted-package acceptance.
4. Owner review and separate publication approval. No public repository, release, or demo is claimed.

Read [scope and distribution](docs/SCOPE.md) for the intended workflow and primary-source comparison. MIT licensed.
