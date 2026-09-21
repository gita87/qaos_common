"""The versioned dictionary 1.0 tabular contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from qaos_common.errors import QAOSCommonError, SchemaValidationError
from qaos_common.rich_content.data_uri import validate_image_data_uri

from .qaos import HeaderValidationResult, ValidationMode, _validate_headers

DICTIONARY_SCHEMA_VERSION = "dictionary/1.0"
DICTIONARY_COLUMNS = ("unique_id", "word", "definition", "image")
# Existing dictionary/1.0 exporters use this marker for absent images.
MISSING_DICTIONARY_IMAGE = "NA"


def validate_dictionary_headers(
    headers: Sequence[str], mode: ValidationMode = "strict"
) -> HeaderValidationResult:
    return _validate_headers(headers, DICTIONARY_COLUMNS, mode, "DICTIONARY_SCHEMA_INVALID")


def validate_dictionary_row(
    row: Mapping[str, Any], *, row_number: int | None = None, seen_ids: set[str] | None = None
) -> None:
    missing = tuple(column for column in DICTIONARY_COLUMNS if column not in row)
    unique_id_value = row.get("unique_id")
    word_value = row.get("word")
    unique_id = "" if unique_id_value is None else str(unique_id_value).strip()
    word = "" if word_value is None else str(word_value).strip()
    if missing or not unique_id or not word:
        raise SchemaValidationError(
            "Dictionary row is invalid",
            code="DICTIONARY_SCHEMA_INVALID",
            stage="validating",
            details={
                "row_number": row_number,
                "missing": missing,
                "unique_id_empty": not unique_id,
                "word_empty": not word,
            },
        )
    if seen_ids is not None and unique_id in seen_ids:
        raise SchemaValidationError(
            "Dictionary unique_id is duplicated",
            code="DICTIONARY_SCHEMA_INVALID",
            stage="validating",
            details={"row_number": row_number, "unique_id": unique_id},
        )
    image_value = row.get("image")
    image = "" if image_value is None else str(image_value).strip()
    if image and image != MISSING_DICTIONARY_IMAGE:
        try:
            validate_image_data_uri(image)
        except QAOSCommonError as exc:
            raise SchemaValidationError(
                "Dictionary image is invalid",
                code="DICTIONARY_SCHEMA_INVALID",
                stage="validating",
                details={"row_number": row_number, "column": "image", "cause_code": exc.code},
            ) from exc
    if seen_ids is not None:
        seen_ids.add(unique_id)


def validate_dictionary_rows(rows: Iterable[Mapping[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        validate_dictionary_row(row, row_number=row_number, seen_ids=seen_ids)


__all__ = [
    "DICTIONARY_COLUMNS",
    "DICTIONARY_SCHEMA_VERSION",
    "MISSING_DICTIONARY_IMAGE",
    "validate_dictionary_headers",
    "validate_dictionary_row",
    "validate_dictionary_rows",
]
