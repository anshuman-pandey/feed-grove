"""Development CLI for migration and ingestion; not the finished reader UI."""
import argparse
import json
import sys
from pathlib import Path
from feeds import FeedError, MAX_BYTES
from library import Library


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='feed-grove.sqlite3')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('import-opml').add_argument('file')
    commands.add_parser('export-opml')
    ingest = commands.add_parser('ingest')
    ingest.add_argument('url'); ingest.add_argument('file')
    listing = commands.add_parser('list')
    listing.add_argument('--query', default='')
    listing.add_argument('--unread', action='store_true')
    listing.add_argument('--starred', action='store_true')
    mark = commands.add_parser('mark')
    mark.add_argument('url'); mark.add_argument('key')
    mark.add_argument('--read', choices=['yes','no'])
    mark.add_argument('--starred', choices=['yes','no'])
    args = parser.parse_args()
    lib = Library(args.db)
    try:
        if args.command in ('import-opml','ingest'):
            with Path(args.file).open('rb') as f:
                raw = f.read(MAX_BYTES+1)
            count = lib.import_opml(raw) if args.command == 'import-opml' else lib.ingest(args.url,raw)
            print(json.dumps({'processed':count}))
        elif args.command == 'export-opml':
            sys.stdout.buffer.write(lib.export_opml())
        elif args.command == 'list':
            print(json.dumps(lib.entries(args.query,args.unread,args.starred),ensure_ascii=True,indent=2))
        elif args.command == 'mark':
            lib.mark(args.url,args.key,read=None if args.read is None else args.read=='yes',
                     starred=None if args.starred is None else args.starred=='yes')
            print('{"updated":true}')
    except (FeedError,OSError) as e:
        print(str(e),file=sys.stderr)
        return 1
    finally:
        lib.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
