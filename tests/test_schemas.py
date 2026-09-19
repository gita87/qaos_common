from __future__ import annotations

import pytest

from qaos_common.errors import SchemaValidationError
from qaos_common.schemas import (
    DICTIONARY_COLUMNS,
    QAOS_COLUMNS,
    validate_dictionary_headers,
    validate_dictionary_rows,
    validate_qaos_headers,
    validate_qaos_row,
)


def test_qaos_schema_is_the_canonical_26_columns() -> None:
    assert len(QAOS_COLUMNS) == 26
    assert QAOS_COLUMNS[0] == "question_number"
    assert QAOS_COLUMNS[-1] == "original_image"
    assert validate_qaos_headers(QAOS_COLUMNS).valid


def test_header_modes_and_order() -> None:
    compatible = validate_qaos_headers((*QAOS_COLUMNS, "future"), mode="compatible")
    assert compatible.extra == ("future",)
    with pytest.raises(SchemaValidationError) as error:
        validate_qaos_headers((*QAOS_COLUMNS, "future"))
    assert error.value.code == "QAOS_SCHEMA_INVALID"
    swapped = list(QAOS_COLUMNS)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    with pytest.raises(SchemaValidationError):
        validate_qaos_headers(swapped, mode="compatible")
    with pytest.raises(ValueError):
        validate_qaos_headers(QAOS_COLUMNS, mode="loose")  # type: ignore[arg-type]


def test_duplicate_and_missing_headers_are_rejected() -> None:
    with pytest.raises(SchemaValidationError) as error:
        validate_qaos_headers((*QAOS_COLUMNS[:-1], QAOS_COLUMNS[-2]))
    assert error.value.details["missing"] == ["original_image"]
    assert error.value.details["duplicates"] == ["train"]


def test_row_and_dictionary_rules() -> None:
    validate_qaos_row(dict.fromkeys(QAOS_COLUMNS, ""), row_number=2)
    with pytest.raises(SchemaValidationError):
        validate_qaos_row({"question_number": "1"}, row_number=2)
    assert validate_dictionary_headers(DICTIONARY_COLUMNS).valid
    rows = [
        {"unique_id": "x", "word": "one", "definition": "", "image": ""},
        {"unique_id": "y", "word": "two", "definition": "", "image": ""},
    ]
    validate_dictionary_rows(rows)
    rows[1]["unique_id"] = "x"
    with pytest.raises(SchemaValidationError) as error:
        validate_dictionary_rows(rows)
    assert error.value.details["row_number"] == 3
