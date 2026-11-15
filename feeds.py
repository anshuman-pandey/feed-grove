"""Bounded, inert feed/OPML parsing. This module performs no network requests."""
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET
from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 2000
ATOM = '{http://www.w3.org/2005/Atom}'
XML_BASE = '{http://www.w3.org/XML/1998/namespace}base'


class FeedError(ValueError):
    pass


def http_url(value, base=''):
    value = value.strip()
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise FeedError('URL contains control characters.')
    try:
        parts = urlsplit(urljoin(base, value))
        if parts.scheme not in ('http', 'https') or not parts.hostname:
            raise ValueError()
        if parts.username is not None or parts.password is not None:
            raise ValueError()
        port = parts.port
        host = parts.hostname.encode('idna').decode('ascii').lower()
        if ':' in host:
            host = '[' + host + ']'
        netloc = host + (f':{port}' if port and port != {'http':80,'https':443}[parts.scheme] else '')
        return urlunsplit((parts.scheme, netloc, parts.path or '/', parts.query, ''))
    except (ValueError, UnicodeError):
        raise FeedError('Use an HTTP(S) URL without credentials.') from None


def document(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise FeedError('XML must be bytes, at most 2 MiB.')
    try:
        root = fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError):
        raise FeedError('Invalid XML or forbidden DTD/entity declaration.') from None
    # Bound nesting and node count before traversing user structure recursively.
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if depth > 32 or count > 20000:
            raise FeedError('XML is too deeply nested or has too many elements.')
        stack.extend((child, depth + 1) for child in node)
    return root


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'br', 'div', 'li') and not self.hidden:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        elif tag in ('p', 'div', 'li') and not self.hidden:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(value)
    return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())


def text(parent, name):
    child = parent.find(name)
    return ''.join(child.itertext()).strip() if child is not None else ''


@dataclass(frozen=True)
class Subscription:
    url: str
    title: str
    folder: tuple[str, ...] = ()


def parse_opml(raw):
    root = document(raw)
    if root.tag != 'opml' or root.find('body') is None:
        raise FeedError('Expected OPML with a body.')
    result = []
    seen = set()

    def walk(parent, path):
        for node in parent.findall('outline'):
            title = (node.get('text') or node.get('title') or '').strip()
            url = node.get('xmlUrl')
            if url is not None:
                url = http_url(url)
                if url not in seen:
                    seen.add(url)
                    result.append(Subscription(url, title or url, path))
                    if len(result) > 500:
                        raise FeedError('OPML exceeds 500 unique feeds.')
            walk(node, path + (title,) if title and url is None else path)

    walk(root.find('body'), ())
    return result


def export_opml(subscriptions):
    root = ET.Element('opml', version='2.0')
    ET.SubElement(ET.SubElement(root, 'head'), 'title').text = 'Feed Grove subscriptions'
    body = ET.SubElement(root, 'body')
    folders = {(): body}
    for sub in subscriptions:
        url = http_url(sub.url)
        path = ()
        for part in sub.folder:
            next_path = path + (part,)
            if next_path not in folders:
                folders[next_path] = ET.SubElement(folders[path], 'outline', text=part)
            path = next_path
        ET.SubElement(folders[path], 'outline', type='rss', text=sub.title, xmlUrl=url)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


@dataclass(frozen=True)
class Entry:
    key: str
    title: str
    url: str
    summary: str
    published: str


def parse_feed(raw, feed_url):
    base = http_url(feed_url)
    root = document(raw)
    is_atom = root.tag == ATOM + 'feed'
    if is_atom:
        nodes = root.findall(ATOM + 'entry')
        title = text(root, ATOM + 'title')
        base = http_url(root.get(XML_BASE, base), base)
    elif root.tag == 'rss' and root.find('channel') is not None:
        channel = root.find('channel')
        nodes = channel.findall('item')
        title = plain(text(channel, 'title'))
    else:
        raise FeedError('Expected RSS 2.0 or Atom 1.0. RSS 1.0/RDF is not supported yet.')
    if len(nodes) > MAX_ITEMS:
        raise FeedError('Feed exceeds 2000 entries.')
    entries, seen = [], set()
    for node in nodes:
        if is_atom:
            title_node = node.find(ATOM + 'title')
            item_title = text(node, ATOM + 'title')
            if title_node is not None and title_node.get('type') == 'html':
                item_title = plain(item_title)
            summary_node = node.find(ATOM + 'summary')
            if summary_node is None:
                summary_node = node.find(ATOM + 'content')
            summary = ''.join(summary_node.itertext()).strip() if summary_node is not None else ''
            if summary_node is not None and summary_node.get('type') == 'html':
                summary = plain(summary)
            links = [n for n in node.findall(ATOM + 'link') if n.get('rel', 'alternate') == 'alternate']
            link = links[0].get('href', '') if links else ''
            node_base = http_url(node.get(XML_BASE, base), base)
            if links and links[0].get(XML_BASE):
                node_base = http_url(links[0].get(XML_BASE), node_base)
            identity = text(node, ATOM + 'id')
            published = text(node, ATOM + 'published') or text(node, ATOM + 'updated')
        else:
            item_title = plain(text(node, 'title'))
            summary = plain(text(node, 'description') or text(node, '{http://purl.org/rss/1.0/modules/content/}encoded'))
            link = text(node, 'link')
            node_base = base
            identity = text(node, 'guid')
            published = text(node, 'pubDate')
        try:
            url = http_url(link, node_base) if link else ''
        except FeedError:
            url = ''  # Unsafe entry links never become clickable URLs.
        identity = identity or url or '\0'.join((item_title, summary, published))
        key = sha256(identity.encode('utf-8')).hexdigest()
        if key not in seen:
            entries.append(Entry(key, item_title or 'Untitled entry', url, summary, published))
            seen.add(key)
    return title or feed_url, entries
