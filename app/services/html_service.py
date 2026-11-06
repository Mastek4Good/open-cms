import re
from html.parser import HTMLParser

import bleach

ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ol",
    "ul",
    "li",
    "span",
]

ALLOWED_ATTRIBUTES = {
    "span": ["class"],
}


class _TextCollector(HTMLParser):
    """Collects the text nodes of an HTML fragment."""

    def __init__(self) -> None:
        # convert_charrefs turns entities like &nbsp; into characters so they
        # count as (strippable) whitespace rather than visible text.
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def has_visible_text(html: str) -> bool:
    """True if the HTML fragment contains any non-whitespace text.

    Uses a real (linear-time) HTML parser rather than a tag-stripping regex:
    patterns like ``<[^>]+>`` backtrack quadratically on untrusted input such as
    a long run of ``<`` characters with no closing ``>``.
    """
    if not html:
        return False
    collector = _TextCollector()
    collector.feed(html)
    collector.close()
    return bool("".join(collector.parts).strip())


def sanitize_html(value: str) -> str:
    if not value:
        return ""
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", value, flags=re.IGNORECASE | re.DOTALL)
    return bleach.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )
