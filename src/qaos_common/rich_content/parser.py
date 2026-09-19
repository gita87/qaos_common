"""Rich-content parsing that exposes only safe visible text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment

from .data_uri import find_data_uris
from .protected_segments import ProtectedSegment, protect_segments

_HTML_RE = re.compile(r"</?[A-Za-z][^>]*>")
_LATEX_RE = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|(?<!\\)\$(?!\$).*?(?<!\\)\$", re.S)
_DICTIONARY_RE = re.compile(
    r"<span\b(?=[^>]*(?:data-dictionary|class=[\"'][^\"']*dictionary))", re.I
)


@dataclass(frozen=True, slots=True)
class ParsedCell:
    original: str
    plain_text: str
    contains_html: bool
    contains_latex: bool
    contains_image: bool
    image_count: int
    contains_dictionary_tag: bool
    protected_segments: tuple[ProtectedSegment, ...]


def parse_cell(value: str | None) -> ParsedCell:
    original = "" if value is None else str(value)
    images = find_data_uris(original)
    contains_latex = _LATEX_RE.search(original) is not None
    contains_html = _HTML_RE.search(original) is not None
    contains_dictionary_tag = _DICTIONARY_RE.search(original) is not None
    protected = protect_segments(original)

    # Remove protected payloads before parsing so they can never leak into visible text.
    scrubbed = protected.text
    for segment in protected.segments:
        if segment.kind == "pattern_2":  # dictionary span: retain only its visible text
            safe_span = re.sub(
                r"data:image/(?:png|jpeg|jpg|gif|webp)\s*;\s*base64\s*,"
                r"(?:[A-Za-z0-9+/=]|[\t\r\n ])+",
                " ",
                segment.value,
                flags=re.I,
            )
            safe_span = _LATEX_RE.sub(" ", safe_span)
            scrubbed = scrubbed.replace(segment.placeholder, safe_span)
    scrubbed = re.sub(r"\[\[QAOS_PROTECTED_[A-Fa-f0-9]+_\d+\]\]", " ", scrubbed)
    if contains_html:
        soup = BeautifulSoup(scrubbed, "lxml")
        for element in soup(["style", "script", "noscript", "template"]):
            element.decompose()
        for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
            comment.extract()
        plain = soup.get_text(" ", strip=True)
    else:
        plain = scrubbed
    plain = re.sub(r"\s+", " ", plain).strip()
    return ParsedCell(
        original=original,
        plain_text=plain,
        contains_html=contains_html,
        contains_latex=contains_latex,
        contains_image=bool(images),
        image_count=len(images),
        contains_dictionary_tag=contains_dictionary_tag,
        protected_segments=protected.segments,
    )


__all__ = ["ParsedCell", "parse_cell"]
