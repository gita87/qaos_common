"""Image data URI detection and bounded decoding."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass

from qaos_common.errors import DataURIError
from qaos_common.limits import DEFAULT_LIMITS, ProcessingLimits

SUPPORTED_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_DATA_URI_RE = re.compile(
    r"data:(?P<mime>image/(?:png|jpeg|jpg|gif|webp))\s*;\s*base64\s*,"
    r"(?P<payload>(?:[A-Za-z0-9+/=]|[\t\r\n ])+)",
    re.IGNORECASE,
)
_FULL_DATA_URI_RE = re.compile(rf"^(?:{_DATA_URI_RE.pattern})$", re.IGNORECASE)
_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


@dataclass(frozen=True, slots=True, repr=False)
class DataURI:
    value: str
    mime_type: str
    payload_start: int
    payload_end: int

    def __repr__(self) -> str:
        return f"DataURI(mime_type={self.mime_type!r}, size={len(self.value)})"


def _normalise_mime(mime: str) -> str:
    mime = mime.lower()
    return "image/jpeg" if mime == "image/jpg" else mime


def find_data_uris(value: str) -> tuple[DataURI, ...]:
    """Locate data URIs without decoding or copying their payload separately."""
    found: list[DataURI] = []
    for match in _DATA_URI_RE.finditer(value):
        found.append(
            DataURI(
                value=match.group(0),
                mime_type=_normalise_mime(match.group("mime")),
                payload_start=match.start("payload"),
                payload_end=match.end("payload"),
            )
        )
    return tuple(found)


def contains_image_data_uri(value: str) -> bool:
    return _DATA_URI_RE.search(value) is not None


def _match_full(value: str) -> re.Match[str]:
    match = _FULL_DATA_URI_RE.fullmatch(value)
    if match is None:
        raise DataURIError("Image data URI is invalid", code="DATA_URI_INVALID")
    return match


def validate_image_data_uri(value: str) -> DataURI:
    match = _match_full(value)
    payload = re.sub(r"\s+", "", match.group("payload"))
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise DataURIError("Image data URI has invalid base64", code="DATA_URI_INVALID") from exc
    mime = _normalise_mime(match.group("mime"))
    if not decoded:
        raise DataURIError("Image data URI payload is empty", code="DATA_URI_INVALID")
    signatures = _SIGNATURES[mime]
    signature_valid = any(decoded.startswith(signature) for signature in signatures)
    if mime == "image/webp":
        signature_valid = decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP"
    if not signature_valid:
        raise DataURIError(
            "Image MIME does not match payload signature", code="IMAGE_MIME_MISMATCH"
        )
    return DataURI(value, mime, match.start("payload"), match.end("payload"))


def decode_data_uri(value: str, *, limits: ProcessingLimits = DEFAULT_LIMITS) -> tuple[bytes, str]:
    match = _match_full(value)
    payload = re.sub(r"\s+", "", match.group("payload"))
    estimated_size = (len(payload) * 3) // 4
    if estimated_size > limits.max_image_bytes + 2:
        raise DataURIError(
            "Decoded image exceeds the configured limit",
            code="CSV_CELL_TOO_LARGE",
            details={"estimated_bytes": estimated_size, "limit": limits.max_image_bytes},
        )
    validated = validate_image_data_uri(value)
    decoded = base64.b64decode(payload, validate=True)
    if len(decoded) > limits.max_image_bytes:
        raise DataURIError(
            "Decoded image exceeds the configured limit",
            code="CSV_CELL_TOO_LARGE",
            details={"actual_bytes": len(decoded), "limit": limits.max_image_bytes},
        )
    return decoded, validated.mime_type


def build_data_uri(data: bytes, mime_type: str) -> str:
    mime = _normalise_mime(mime_type)
    if mime not in SUPPORTED_IMAGE_MIMES:
        raise DataURIError(
            "Unsupported image MIME type",
            code="DATA_URI_INVALID",
            details={"mime_type": mime_type},
        )
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


__all__ = [
    "SUPPORTED_IMAGE_MIMES",
    "DataURI",
    "build_data_uri",
    "contains_image_data_uri",
    "decode_data_uri",
    "find_data_uris",
    "validate_image_data_uri",
]
