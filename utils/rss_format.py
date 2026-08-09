import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

DMGUILD_BASE = "https://www.dmsguild.com/"
PUBLISHER_RE = re.compile(r"^Publisher:\s*(.+)$", re.IGNORECASE)
PRICE_RE = re.compile(r"^Price:\s*(\$[\d.]+)$", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)


class _HTMLToText(HTMLParser):
    """Convert simple feed HTML into readable plain text."""

    BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self) -> str:
        text = html.unescape("".join(self._parts))
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_plain_text(raw: str) -> str:
    if not raw:
        return ""
    parser = _HTMLToText()
    parser.feed(raw)
    return parser.get_text()


def format_author_name(name: str) -> str:
    return name.replace("_", " ").strip()


def entry_summary_html(entry: dict[str, Any]) -> str:
    summary = entry.get("summary")
    if summary:
        return summary

    content = entry.get("content")
    if isinstance(content, list) and content:
        return content[0].get("value", "") or ""
    if isinstance(content, dict):
        return content.get("value", "") or ""
    return ""


def entry_author_name(entry: dict[str, Any]) -> str | None:
    author = entry.get("author")
    if author:
        return format_author_name(str(author))

    author_detail = entry.get("author_detail") or {}
    name = author_detail.get("name")
    if name:
        return format_author_name(str(name))
    return None


def extract_image_url(raw_html: str, *, base_url: str = DMGUILD_BASE) -> str | None:
    if not raw_html:
        return None

    match = IMG_SRC_RE.search(raw_html)
    if not match:
        return None

    src = html.unescape(match.group(1)).strip()
    if not src:
        return None
    if src.startswith("//"):
        return f"https:{src}"
    if src.startswith("/"):
        return urljoin(base_url, src)
    if src.startswith("http"):
        return src
    return None


def entry_image_url(entry: dict[str, Any]) -> str | None:
    for thumb in entry.get("media_thumbnail") or []:
        url = thumb.get("url")
        if url:
            return url

    for media in entry.get("media_content") or []:
        url = media.get("url")
        if url and media.get("medium") != "document":
            return url

    image = entry.get("image")
    if isinstance(image, dict) and image.get("href"):
        return image["href"]

    for enclosure in entry.get("enclosures") or []:
        if enclosure.get("type", "").startswith("image/"):
            return enclosure.get("href")

    raw_html = entry_summary_html(entry)
    link = entry.get("link") or DMGUILD_BASE
    base_url = "/".join(link.split("/")[:3]) + "/" if "://" in link else DMGUILD_BASE
    return extract_image_url(raw_html, base_url=base_url)


def parse_feed_summary(text: str, title: str) -> dict[str, str | None]:
    publisher = None
    price = None
    body_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if body_lines and body_lines[-1] != "":
                body_lines.append("")
            continue

        publisher_match = PUBLISHER_RE.match(stripped)
        if publisher_match and publisher is None:
            publisher = publisher_match.group(1).strip()
            continue

        price_match = PRICE_RE.match(stripped)
        if price_match:
            price = price_match.group(1).strip()
            continue

        if stripped.casefold() == title.casefold():
            continue

        body_lines.append(stripped)

    description = "\n".join(body_lines).strip()
    description = re.sub(r"\n{3,}", "\n\n", description)
    if len(description) > 400:
        description = description[:397] + "..."

    return {
        "publisher": publisher,
        "price": price,
        "description": description or None,
    }


def build_entry_content(entry: dict[str, Any]) -> dict[str, str | None]:
    title = (entry.get("title") or "No title").strip()
    raw_html = entry_summary_html(entry)
    plain = html_to_plain_text(raw_html)
    parsed = parse_feed_summary(plain, title)

    author = entry_author_name(entry) or parsed["publisher"]
    return {
        "title": title[:256],
        "author": author,
        "price": parsed["price"],
        "description": parsed["description"],
        "image_url": entry_image_url(entry),
    }
