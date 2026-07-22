"""
Atlas v21 - Module 6: deterministic parsing into plain structures.

Every parser here returns dicts/lists/strings only (or raises a
ParsingError) - never a live object, never anything that could
execute. HTML/XML parsing uses the standard library only (no browser
engine involved).
"""

import json
import re
from html.parser import HTMLParser
from xml.etree import ElementTree

from collector_intelligence.ingestion_normalization import clean_text


class ParsingError(Exception):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type
        self.message = message


# ---------------------------------------------------------------
# JSON
# ---------------------------------------------------------------

def parse_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ParsingError("INVALID_JSON", f"Could not parse JSON: {exc}") from exc


# ---------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def parse_rss_or_atom(text):
    """
    Returns {"feed_title": str|None, "feed_link": str|None, "items": [...]}.
    Each item: {"title","link","summary","content","published_at","author","guid","categories"}.
    """
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ParsingError("INVALID_RSS", f"Could not parse RSS/Atom XML: {exc}") from exc

    if root.tag == "rss" or root.tag.endswith("}rss"):
        return _parse_rss_channel(root)

    if root.tag == f"{_ATOM_NS}feed" or root.tag.endswith("}feed"):
        return _parse_atom_feed(root)

    raise ParsingError(
        "INVALID_RSS", f"Root element {root.tag!r} is neither <rss> nor <feed>.",
    )


def _text(element, path, ns=None):
    found = element.find(path, ns) if ns else element.find(path)
    return clean_text(found.text) if found is not None and found.text else None


def _parse_rss_channel(root):
    channel = root.find("channel")
    if channel is None:
        raise ParsingError("INVALID_RSS", "RSS document has no <channel> element.")

    items = []
    for item in channel.findall("item"):
        categories = [
            clean_text(c.text) for c in item.findall("category") if c.text
        ]
        items.append({
            "title": _text(item, "title"),
            "link": _text(item, "link"),
            "summary": _text(item, "description"),
            "content": _text(item, "{http://purl.org/rss/1.0/modules/content/}encoded"),
            "published_at": _text(item, "pubDate"),
            "author": _text(item, "author") or _text(item, "{http://purl.org/dc/elements/1.1/}creator"),
            "guid": _text(item, "guid"),
            "categories": categories,
        })

    return {
        "feed_title": _text(channel, "title"),
        "feed_link": _text(channel, "link"),
        "items": items,
    }


def _parse_atom_feed(root):
    ns = {"a": _ATOM_NS.strip("{}")}

    def find_link(element):
        link_element = element.find(f"{_ATOM_NS}link")
        return link_element.get("href") if link_element is not None else None

    items = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        author_element = entry.find(f"{_ATOM_NS}author/{_ATOM_NS}name")
        categories = [
            c.get("term") for c in entry.findall(f"{_ATOM_NS}category") if c.get("term")
        ]
        items.append({
            "title": _text(entry, f"{_ATOM_NS}title"),
            "link": find_link(entry),
            "summary": _text(entry, f"{_ATOM_NS}summary"),
            "content": _text(entry, f"{_ATOM_NS}content"),
            "published_at": _text(entry, f"{_ATOM_NS}updated") or _text(entry, f"{_ATOM_NS}published"),
            "author": clean_text(author_element.text) if author_element is not None and author_element.text else None,
            "guid": _text(entry, f"{_ATOM_NS}id"),
            "categories": categories,
        })

    return {
        "feed_title": _text(root, f"{_ATOM_NS}title"),
        "feed_link": find_link(root),
        "items": items,
    }


# ---------------------------------------------------------------
# Generic XML -> nested dict
# ---------------------------------------------------------------

def parse_xml(text):
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ParsingError("INVALID_XML", f"Could not parse XML: {exc}") from exc

    return _element_to_dict(root)


def _element_to_dict(element):
    result = dict(element.attrib)
    children = list(element)

    if not children:
        text = clean_text(element.text) if element.text else None
        if result:
            if text:
                result["_text"] = text
            return result
        return text

    for child in children:
        value = _element_to_dict(child)
        tag = child.tag.split("}")[-1]  # strip namespace
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(value)
        else:
            result[tag] = value

    return result


# ---------------------------------------------------------------
# HTML -> title/body text + JSON-LD structured data
# ---------------------------------------------------------------

class _StructuredHTMLParser(HTMLParser):
    _BLOCK_TAGS = {
        "p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section",
    }
    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.h1_parts = []
        self.body_parts = []
        self.json_ld_blocks = []
        self._in_title = False
        self._in_h1 = False
        self._skip_depth = 0
        self._current_script_type = None

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            if tag == "script":
                attr_dict = dict(attrs)
                self._current_script_type = attr_dict.get("type", "")
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag in self._BLOCK_TAGS:
            self.body_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._skip_depth:
            if self._current_script_type == "application/ld+json":
                self.json_ld_blocks.append(data)
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)
        self.body_parts.append(data)


def parse_html(text):
    """
    Returns {"title": str|None, "h1": str|None, "body": str,
    "json_ld": [dict, ...]}. json_ld entries that fail to parse as
    JSON are silently skipped (malformed structured data, not fatal).
    """
    parser = _StructuredHTMLParser()

    try:
        parser.feed(text)
    except Exception as exc:
        raise ParsingError("INVALID_CONTENT", f"Could not parse HTML: {exc}") from exc

    json_ld = []
    for block in parser.json_ld_blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        json_ld.extend(parsed if isinstance(parsed, list) else [parsed])

    return {
        "title": clean_text("".join(parser.title_parts)) or None,
        "h1": clean_text("".join(parser.h1_parts)) or None,
        "body": clean_text("".join(parser.body_parts)),
        "json_ld": json_ld,
    }


def parse_plain_text(text):
    return clean_text(text)


def find_json_ld_of_type(json_ld_blocks, schema_type):
    for block in json_ld_blocks:
        block_type = block.get("@type")
        types = block_type if isinstance(block_type, list) else [block_type]
        if schema_type in types:
            return block
    return None
