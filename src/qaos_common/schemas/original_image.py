"""Canonical and legacy-safe original_image metadata."""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from qaos_common.errors import OriginalImageError
from qaos_common.rich_content.data_uri import validate_image_data_uri


class OriginalImageRecord(TypedDict):
    column: str
    index: int
    original_mime: str
    original_data_uri: str
    style: NotRequired[str]
    value_path: NotRequired[list[str | int]]


_FIELDS = ("column", "index", "original_mime", "original_data_uri")


def validate_original_image(record: Mapping[str, Any]) -> OriginalImageRecord:
    if not isinstance(record, Mapping):
        raise OriginalImageError(
            "original_image record must be an object", code="ORIGINAL_IMAGE_INVALID"
        )
    missing = tuple(field for field in _FIELDS if field not in record)
    index = record.get("index")
    if (
        missing
        or not isinstance(record.get("column"), str)
        or not str(record.get("column", "")).strip()
        or isinstance(index, bool)
        or not isinstance(index, int)
        or index < 0
        or not isinstance(record.get("original_mime"), str)
        or not isinstance(record.get("original_data_uri"), str)
    ):
        raise OriginalImageError(
            "original_image record has invalid fields",
            code="ORIGINAL_IMAGE_INVALID",
            details={"missing": missing, "index": index},
        )
    uri = str(record["original_data_uri"])
    parsed = validate_image_data_uri(uri)
    mime = str(record["original_mime"]).lower()
    if parsed.mime_type != mime:
        raise OriginalImageError(
            "original_mime does not match original_data_uri",
            code="ORIGINAL_IMAGE_INVALID",
            details={"original_mime": mime, "data_uri_mime": parsed.mime_type},
        )
    result: OriginalImageRecord = {
        "column": str(record["column"]),
        "index": index,
        "original_mime": mime,
        "original_data_uri": uri,
    }
    if "style" in record:
        if not isinstance(record["style"], str):
            raise OriginalImageError("Invalid style", code="ORIGINAL_IMAGE_INVALID")
        result["style"] = record["style"]
    if "value_path" in record:
        path = record["value_path"]
        if not isinstance(path, list) or any(
            isinstance(x, bool) or not isinstance(x, (str, int)) for x in path
        ):
            raise OriginalImageError("Invalid value_path", code="ORIGINAL_IMAGE_INVALID")
        result["value_path"] = list(path)
    return result


def parse_original_images(
    value: str | Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> list[OriginalImageRecord]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return []
    parsed: Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError) as exc:
                raise OriginalImageError(
                    "original_image is neither valid JSON nor supported legacy data",
                    code="ORIGINAL_IMAGE_INVALID",
                ) from exc
    if isinstance(parsed, Mapping):
        parsed = [parsed]
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        raise OriginalImageError(
            "original_image must contain an array or object", code="ORIGINAL_IMAGE_INVALID"
        )
    return [validate_original_image(item) for item in parsed]


def serialize_original_images(records: Sequence[Mapping[str, Any]]) -> str:
    validated = [validate_original_image(record) for record in records]
    return json.dumps(validated, ensure_ascii=False, separators=(",", ":"))


def append_original_image(value: str | None, record: Mapping[str, Any]) -> str:
    records = parse_original_images(value)
    records.append(validate_original_image(record))
    return serialize_original_images(records)


__all__ = [
    "OriginalImageRecord",
    "append_original_image",
    "parse_original_images",
    "serialize_original_images",
    "validate_original_image",
]
