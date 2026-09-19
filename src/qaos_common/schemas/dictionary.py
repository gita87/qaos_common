"""The versioned dictionary 1.0 tabular contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from qaos_common.errors import SchemaValidationError
from qaos_common.rich_content.data_uri import validate_image_data_uri

from .qaos import HeaderValidationResult, ValidationMode, _validate_headers

DICTIONARY_SCHEMA_VERSION = "dictionary/1.0"
DICTIONARY_COLUMNS = ("unique_id", "word", "definition", "image")


def validate_dictionary_headers(
    headers: Sequence[str], mode: ValidationMode = "strict"
) -> HeaderValidationResult:
    return _validate_headers(headers, DICTIONARY_COLUMNS, mode, "DICTIONARY_SCHEMA_INVALID")


def validate_dictionary_row(
    row: Mapping[str, Any], *, row_number: int | None = None, seen_ids: set[str] | None = None
) -> None:
    missing = tuple(column for column in DICTIONARY_COLUMNS if column not in row)
    unique_id = str(row.get("unique_id", "")).strip()
    word = str(row.get("word", "")).strip()
    if missing or not unique_id or not word:
        raise SchemaValidationError(
            "Dictionary row is invalid",
            code="DICTIONARY_SCHEMA_INVALID",
            details={
                "row_number": row_number,
                "missing": missing,
                "unique_id_empty": not unique_id,
                "word_empty": not word,
            },
        )
    if seen_ids is not None:
        if unique_id in seen_ids:
            raise SchemaValidationError(
                "Dictionary unique_id is duplicated",
                code="DICTIONARY_SCHEMA_INVALID",
                details={"row_number": row_number, "unique_id": unique_id},
            )
        seen_ids.add(unique_id)
    image = str(row.get("image", "")).strip()
    if image:
        validate_image_data_uri(image)


def validate_dictionary_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        validate_dictionary_row(row, row_number=row_number, seen_ids=seen_ids)


__all__ = [
    "DICTIONARY_COLUMNS",
    "DICTIONARY_SCHEMA_VERSION",
    "validate_dictionary_headers",
    "validate_dictionary_row",
    "validate_dictionary_rows",
]
