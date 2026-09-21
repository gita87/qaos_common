import copy
import json

import pytest

from qaos_common.errors import SchemaValidationError
from qaos_common.rich_content import build_data_uri
from qaos_common.schemas import (
    QAOS_COLUMNS,
    validate_dictionary_row,
    validate_qaos_row,
)


def row():
    return dict.fromkeys(QAOS_COLUMNS, "")


@pytest.mark.parametrize("column", ["train", "flip_front", "flip_back"])
@pytest.mark.parametrize("value", ["not-json", "{}", "null", "[NaN]", 7, {"a": 1}])
def test_rejects_invalid_arrays_with_row_and_column_context(column, value):
    with pytest.raises(SchemaValidationError) as caught:
        validate_qaos_row({**row(), column: value}, row_number=9)
    error = caught.value
    assert error.code == "QAOS_SCHEMA_INVALID"
    assert error.stage == "validating"
    assert error.details == {"row_number": 9, "column": column}


def test_strict_and_compatible_modes_keep_cell_validation():
    sample = {**row(), "extra": "note"}
    with pytest.raises(SchemaValidationError) as caught:
        validate_qaos_row(sample, row_number=3)
    assert caught.value.details["extra"] == ["extra"]
    assert caught.value.details["row_number"] == 3
    validate_qaos_row(sample, mode="compatible")
    with pytest.raises(SchemaValidationError):
        validate_qaos_row({**sample, "train": "bad"}, mode="compatible")
    with pytest.raises(ValueError):
        validate_qaos_row(row(), mode="typo")


@pytest.mark.parametrize("value", ["not-json", "42", "[{}]", 42, [None]])
def test_invalid_provenance_has_consistent_context(value):
    with pytest.raises(SchemaValidationError) as caught:
        validate_qaos_row({**row(), "original_image": value}, row_number=4)
    assert caught.value.details == {"row_number": 4, "column": "original_image"}


@pytest.mark.parametrize("container", [lambda v: [v], lambda v: v, lambda v: json.dumps([v]), repr])
def test_native_and_legacy_cells_validate_without_mutation(container):
    record = {
        "column": "question_text",
        "index": 0,
        "original_mime": "image/png",
        "original_data_uri": build_data_uri(b"\x89PNG\r\n\x1a\nminimal", "image/png"),
        "style": "width:10px",
        "value_path": ["0", "front"],
    }
    sample = {
        **row(),
        "original_image": container(record),
        "train": ["one\ntwo", ["nested"]],
        "flip_front": ("café",),
        "flip_back": '["  back  "]',
    }
    before = copy.deepcopy(sample)
    validate_qaos_row(sample)
    assert sample == before


@pytest.mark.parametrize("value", [None, "", "NA"])
def test_dictionary_accepts_existing_missing_image_values(value):
    validate_dictionary_row(
        {"unique_id": "'0001", "word": "apple", "definition": "fruit", "image": value}
    )


def test_failed_dictionary_validation_does_not_claim_an_id():
    seen = set()
    sample = {"unique_id": "1", "word": "word", "definition": "", "image": "bad"}
    with pytest.raises(SchemaValidationError) as caught:
        validate_dictionary_row(sample, row_number=7, seen_ids=seen)
    assert seen == set()
    assert caught.value.details["row_number"] == 7
    validate_dictionary_row({**sample, "image": "NA"}, seen_ids=seen)
    assert seen == {"1"}


@pytest.mark.parametrize("column", ["word", "unique_id"])
def test_dictionary_none_is_not_a_nonempty_string(column):
    with pytest.raises(SchemaValidationError):
        validate_dictionary_row(
            {"unique_id": "1", "word": "word", "definition": "", "image": "NA", column: None}
        )
