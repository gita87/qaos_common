"""Rich-content inspection with sensitive-payload protection."""

from .data_uri import (
    DataURI,
    build_data_uri,
    contains_image_data_uri,
    decode_data_uri,
    find_data_uris,
    validate_image_data_uri,
)
from .parser import ParsedCell, parse_cell
from .protected_segments import (
    ProtectedContent,
    ProtectedSegment,
    protect_segments,
    restore_segments,
)

__all__ = [
    "DataURI",
    "ParsedCell",
    "ProtectedContent",
    "ProtectedSegment",
    "build_data_uri",
    "contains_image_data_uri",
    "decode_data_uri",
    "find_data_uris",
    "parse_cell",
    "protect_segments",
    "restore_segments",
    "validate_image_data_uri",
]
