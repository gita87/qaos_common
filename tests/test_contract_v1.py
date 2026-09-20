import csv
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from qaos_common import DEFAULT_LIMITS
from qaos_common.csvio import QAOSCSVProfile, QAOSCSVReader, QAOSCSVWriter, serialize_csv
from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.schemas import (
    ARRAY_COLUMNS,
    QAOS_COLUMNS,
    QAOS_SCHEMA_VERSION,
    RICH_CONTENT_FORMAT,
    serialize_array,
)


def test_contract_identity_and_arrays():
    assert QAOS_SCHEMA_VERSION == "qaos/1.0"
    assert RICH_CONTENT_FORMAT == "qaos-html/1"
    assert serialize_array(["café", "one\ntwo"]) == '["café","one\\ntwo"]'
    assert serialize_array(None) == serialize_array("") == "[]"
    for invalid in ("{}", "null", "[NaN]", 7):
        with pytest.raises(ValueError):
            serialize_array(invalid)


@pytest.mark.parametrize("quoting", [csv.QUOTE_ALL, csv.QUOTE_MINIMAL])
def test_bytes_stream_path_equivalence(tmp_path, quoting):
    row = dict.fromkeys(QAOS_COLUMNS, "")
    row.update(
        question_text='café\r\n"quoted"\ttext\rnext\nlast',
        train=["one\ntwo"],
        flip_front=["<b>front</b>"],
    )
    profile = QAOSCSVProfile(quoting=quoting)
    payload = serialize_csv([row], profile=profile)
    stream = io.BytesIO()
    with QAOSCSVWriter(stream, profile=profile) as writer:
        writer.write_row(row)
    path = tmp_path / "out.tsv"
    with QAOSCSVWriter(path, profile=profile) as writer:
        writer.write_row(row)
    assert not stream.closed
    assert payload == stream.getvalue() == path.read_bytes()
    assert not payload.startswith(b"\xef\xbb\xbf")
    assert payload.count(b"\n") == 2 and b"\r" not in payload
    with QAOSCSVReader(payload) as reader:
        result = next(iter(reader))[1]
    assert result["question_text"] == 'café "quoted"\ttext next last'
    assert json.loads(result["train"]) == ["one\ntwo"]
    for name in ARRAY_COLUMNS:
        assert isinstance(json.loads(result[name]), list)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(delimiter=","),
        dict(write_bom=True),
        dict(line_ending="\r\n"),
        dict(quoting=3),
        dict(encoding="utf-8-sig"),
    ],
)
def test_profile_rejects_non_contract_output(kwargs):
    with pytest.raises(ValueError):
        QAOSCSVProfile(**kwargs)


def test_limits_do_not_write_rejected_rows_and_clean_failed_enter(tmp_path):
    stream = io.BytesIO()
    limits = replace(DEFAULT_LIMITS, max_output_bytes=8)
    with pytest.raises(CSVLimitError), QAOSCSVWriter(stream, columns=("x",), limits=limits) as w:
        w.write_row({"x": "too much"})
    assert stream.getvalue() == b'"x"\n'
    assert not stream.closed
    with pytest.raises(CSVLimitError), QAOSCSVWriter(tmp_path / "x", limits=limits):
        pass
    assert list(tmp_path.iterdir()) == []


def test_error_envelope_redacts_stage():
    error = QAOSCommonError("failed", code="EXAMPLE", stage="writing", details={"data": b"secret"})
    assert error.to_dict() == dict(
        code="EXAMPLE", message="failed", stage="writing", details={"data": "<redacted-bytes:6>"}
    )
    assert QAOSCommonError("x").to_dict()["stage"] is None


def test_real_converter_output_round_trips():
    payload = (Path(__file__).parent / "fixtures" / "converter.tsv").read_bytes()
    with QAOSCSVReader(payload) as reader:
        assert reader.headers == QAOS_COLUMNS
        rows = [row for _, row in reader]
    assert serialize_csv(rows) == payload
