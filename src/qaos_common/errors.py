"""Stable and payload-safe public errors."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_DATA_URI_RE = re.compile(
    r"data:[^;,\s]+(?:;[^,\s]*)?;base64\s*,\s*[A-Za-z0-9+/=\s]+", re.IGNORECASE
)
_LONG_BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{80,}={0,2}")


def redact_sensitive(value: Any) -> Any:
    """Return a recursively redacted, log-safe representation."""
    if isinstance(value, str):
        value = _DATA_URI_RE.sub("<redacted-data-uri>", value)
        return _LONG_BASE64_RE.sub("<redacted-base64>", value)
    if isinstance(value, Mapping):
        return {str(k): redact_sensitive(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return f"<redacted-bytes:{len(value)}>"
    return value


class QAOSCommonError(Exception):
    """Base exception with a stable code and safe structured details."""

    default_code = "QAOS_COMMON_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        stage: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.stage = redact_sensitive(stage)
        self.code = code or self.default_code
        self.message = str(redact_sensitive(message))
        self.details = redact_sensitive(dict(details or {}))
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class SchemaValidationError(QAOSCommonError):
    """Invalid QAOS or dictionary schema."""


class CSVLimitError(QAOSCommonError):
    """A CSV input, cell, or output exceeded configured limits."""


class DataURIError(QAOSCommonError):
    """Invalid or inconsistent image data URI."""


class OriginalImageError(QAOSCommonError):
    """Invalid original_image metadata."""


class ProtectedSegmentError(QAOSCommonError):
    """Protected content could not be safely restored."""


class ProcessCancelledError(QAOSCommonError):
    """Cooperative processing cancellation."""

    default_code = "PROCESS_CANCELLED"


__all__ = [
    "CSVLimitError",
    "DataURIError",
    "OriginalImageError",
    "ProcessCancelledError",
    "ProtectedSegmentError",
    "QAOSCommonError",
    "SchemaValidationError",
    "redact_sensitive",
]
