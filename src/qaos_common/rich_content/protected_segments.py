"""Collision-safe protection and exact restoration of rich-content segments."""

from __future__ import annotations

import re
import secrets
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from qaos_common.errors import ProtectedSegmentError

from .data_uri import _DATA_URI_RE

_PLACEHOLDER_RE = re.compile(r"\[\[QAOS_PROTECTED_[A-Fa-f0-9]+_\d+\]\]")
_DICTIONARY_SPAN_RE = re.compile(
    r"<span\b(?=[^>]*(?:data-dict-id\s*=|data-dictionary|class=[\"'][^\"']*dictionary))"
    r"[^>]*>.*?</span\s*>",
    re.I | re.S,
)
_LATEX_RE = re.compile(
    r"\\begin\{([^{}]+)\}.*?\\end\{\1\}"
    r"|\$\$.*?\$\$|\\\[.*?\\\]|\\\(.*?\\\)|(?<!\\)\$(?!\$).*?(?<!\\)\$",
    re.S,
)
_DEFAULT_PATTERNS = (
    re.compile(r"<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>", re.I | re.S),
    _DATA_URI_RE,
    _DICTIONARY_SPAN_RE,
    _LATEX_RE,
    re.compile(r"(?<=\s)(?:[A-Za-z_:][-\w:.]*\s*=\s*(?:\"[^\"]*\"|'[^']*'))"),
)


@dataclass(frozen=True, slots=True, repr=False)
class ProtectedSegment:
    placeholder: str
    value: str
    kind: str

    def __repr__(self) -> str:
        return (
            f"ProtectedSegment(placeholder={self.placeholder!r}, "
            f"kind={self.kind!r}, size={len(self.value)})"
        )


@dataclass(frozen=True, slots=True, repr=False)
class ProtectedContent:
    text: str
    segments: tuple[ProtectedSegment, ...]
    nonce: str

    def __repr__(self) -> str:
        return f"ProtectedContent(text={self.text!r}, segments={len(self.segments)})"

    def restore(self, text: str | None = None) -> str:
        return restore_segments(self if text is None else text, self.segments)


def protect_segments(
    value: str,
    *,
    patterns: Sequence[re.Pattern[str] | str] = (),
    literal_segments: Iterable[str] = (),
) -> ProtectedContent:
    """Protect default and caller-supplied segments in one left-to-right pass."""
    nonce = secrets.token_hex(12)
    while f"[[QAOS_PROTECTED_{nonce}_" in value:
        nonce = secrets.token_hex(12)
    compiled = list(_DEFAULT_PATTERNS)
    compiled.extend(
        re.compile(pattern, re.S) if isinstance(pattern, str) else pattern for pattern in patterns
    )
    literals = sorted({item for item in literal_segments if item}, key=len, reverse=True)

    candidates: list[tuple[int, int, str, str]] = []
    for item in literals:
        for match in re.finditer(re.escape(item), value):
            candidates.append((match.start(), match.end(), "literal", match.group(0)))
    for index, pattern in enumerate(compiled):
        for match in pattern.finditer(value):
            candidates.append((match.start(), match.end(), f"pattern_{index}", match.group(0)))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    accepted: list[tuple[int, int, str, str]] = []
    cursor = -1
    for candidate in candidates:
        if candidate[0] >= cursor:
            accepted.append(candidate)
            cursor = candidate[1]

    output: list[str] = []
    segments: list[ProtectedSegment] = []
    cursor = 0
    for start, end, kind, raw in accepted:
        output.append(value[cursor:start])
        placeholder = f"[[QAOS_PROTECTED_{nonce}_{len(segments)}]]"
        output.append(placeholder)
        segments.append(ProtectedSegment(placeholder, raw, kind))
        cursor = end
    output.append(value[cursor:])
    return ProtectedContent("".join(output), tuple(segments), nonce)


def restore_segments(
    content: ProtectedContent | str, segments: Sequence[ProtectedSegment] | None = None
) -> str:
    if isinstance(content, ProtectedContent):
        text = content.text
        expected = content.segments
    else:
        text = content
        if segments is None:
            raise TypeError("segments are required when restoring a string")
        expected = tuple(segments)
    expected_tokens = {segment.placeholder for segment in expected}
    unknown = set(_PLACEHOLDER_RE.findall(text)) - expected_tokens
    counts = {segment.placeholder: text.count(segment.placeholder) for segment in expected}
    invalid = {token: count for token, count in counts.items() if count != 1}
    if unknown or invalid:
        raise ProtectedSegmentError(
            "Protected placeholders are missing, repeated, or unknown",
            code="PROTECTED_SEGMENT_INVALID",
            details={"unknown_count": len(unknown), "invalid_counts": invalid},
        )
    for segment in expected:
        text = text.replace(segment.placeholder, segment.value)
    return text


__all__ = [
    "ProtectedContent",
    "ProtectedSegment",
    "protect_segments",
    "restore_segments",
]
