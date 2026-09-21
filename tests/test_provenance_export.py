import copy
import io
import json

import pytest

from qaos_common.csvio import CSVProfile, QAOSCSVReader, QAOSCSVWriter, serialize_csv
from qaos_common.errors import QAOSCommonError
from qaos_common.schemas import QAOS_COLUMNS, validate_qaos_row


def record():
    return {
        "column": "question_text",
        "index": 0,
        "original_mime": "image/png",
        "original_data_uri": "data:image/png;base64,iVBORw0KGgptaW5pbWFs",
        "style": "width:20px;\nheight:20px",
        "value_path": ["0", "front"],
    }


@pytest.mark.parametrize(
    "form",
    [
        lambda r: [r],
        lambda r: r,
        lambda r: (r,),
        lambda r: json.dumps([r], indent=2),
        lambda r: json.dumps(r),
        lambda r: repr([r]),
        lambda r: repr(r),
    ],
)
def test_accepted_provenance_is_exported_as_compact_json_on_every_destination(tmp_path, form):
    row = {**dict.fromkeys(QAOS_COLUMNS, ""), "original_image": form(record())}
    before = copy.deepcopy(row)
    validate_qaos_row(row)
    payload = serialize_csv([row])
    stream = io.BytesIO()
    with QAOSCSVWriter(stream) as writer:
        writer.write_row(row)
    path = tmp_path / "output.tsv"
    with QAOSCSVWriter(path) as writer:
        writer.write_row(row)
    assert payload == path.read_bytes() == stream.getvalue()
    assert row == before and not stream.closed
    assert payload.count(b"\n") == 2
    with QAOSCSVReader(payload) as reader:
        actual = next(iter(reader))[1]
    validate_qaos_row(actual)
    value = actual["original_image"]
    assert json.loads(value) == [record()]
    assert value == json.dumps([record()], ensure_ascii=False, separators=(",", ":"))


@pytest.mark.parametrize("empty", [None, "", "  ", [], (), "[]"])
def test_missing_provenance_has_one_canonical_representation(empty):
    row = {**dict.fromkeys(QAOS_COLUMNS, ""), "original_image": empty}
    with QAOSCSVReader(serialize_csv([row])) as reader:
        assert next(iter(reader))[1]["original_image"] == "[]"


@pytest.mark.parametrize("invalid", ["not-json", "[{}]", 5, {**record(), "index": -1}])
def test_bad_provenance_is_rejected_before_a_row_is_written(tmp_path, invalid):
    row = {**dict.fromkeys(QAOS_COLUMNS, ""), "original_image": invalid}
    path = tmp_path / "output.tsv"
    with pytest.raises(QAOSCommonError) as caught, QAOSCSVWriter(path) as writer:
        writer.write_row(row)
    assert not path.exists() and list(tmp_path.iterdir()) == []
    assert caught.value.to_dict() == {
        "code": "QAOS_SCHEMA_INVALID",
        "message": "Invalid QAOS original_image cell",
        "stage": "writing",
        "details": {"row_number": 2, "column": "original_image"},
    }


def test_preservation_profile_does_not_rewrite_legacy_provenance():
    value = repr([record()])
    payload = serialize_csv(
        [{"original_image": value}], columns=("original_image",), profile=CSVProfile()
    )
    with QAOSCSVReader(payload) as reader:
        assert next(iter(reader))[1]["original_image"] == value
