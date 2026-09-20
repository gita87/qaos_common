from __future__ import annotations

import io
from pathlib import Path

import pytest

from qaos_common.csvio import (
    CSVReader,
    DictionaryCSVProfile,
    DictionaryCSVWriter,
    QAOSCSVProfile,
    QAOSCSVReader,
    QAOSCSVWriter,
)
from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.limits import ProcessingLimits
from qaos_common.schemas import DICTIONARY_COLUMNS, QAOS_COLUMNS, validate_qaos_headers


def qaos_row(text: str = "Question") -> dict[str, str]:
    row = dict.fromkeys(QAOS_COLUMNS, "")
    row["question_number"] = "1"
    row["question_text"] = text
    return row


def test_qaos_round_trip_is_streaming_and_exact(tmp_path: Path) -> None:
    target = tmp_path / "qaos.tsv"
    with QAOSCSVWriter(target, profile=QAOSCSVProfile(scalar_newlines="preserve")) as writer:
        writer.write_row(qaos_row("line 1\nline 2\tquoted"))
    with QAOSCSVReader(target) as reader:
        validate_qaos_headers(reader.headers)
        iterator = iter(reader)
        row_number, row = next(iterator)
        assert row_number == 3  # quoted cell contains a physical newline
        assert row["question_text"] == "line 1\nline 2\tquoted"
        with pytest.raises(StopIteration):
            next(iterator)


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_dictionary_bom_and_line_endings(tmp_path: Path, line_ending: str) -> None:
    target = tmp_path / f"dictionary-{len(line_ending)}.tsv"
    profile = DictionaryCSVProfile(write_bom=True, line_ending=line_ending)
    with DictionaryCSVWriter(target, profile=profile) as writer:
        writer.write_row({"unique_id": "1", "word": "café", "definition": "d", "image": ""})
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and line_ending.encode() in raw
    with CSVReader(raw, profile=profile) as reader:
        assert reader.headers == DICTIONARY_COLUMNS
        assert next(iter(reader))[1]["word"] == "café"


def test_binary_and_text_streams_remain_usable() -> None:
    raw = b"a\tb\n1\t2\n"
    binary = io.BytesIO(raw)
    with CSVReader(binary) as reader:
        assert next(iter(reader))[1] == {"a": "1", "b": "2"}
    assert not binary.closed
    text = io.StringIO(raw.decode())
    with CSVReader(text) as reader:
        assert next(iter(reader))[1]["a"] == "1"
    assert not text.closed


def test_large_cell_and_cell_limit_reporting(tmp_path: Path) -> None:
    large = "x" * (11 * 1024 * 1024)
    target = tmp_path / "large.tsv"
    generous = ProcessingLimits(
        max_upload_bytes=16 * 1024 * 1024,
        max_cell_bytes=12 * 1024 * 1024,
        max_output_bytes=16 * 1024 * 1024,
        max_image_bytes=10,
    )
    with QAOSCSVWriter(target, limits=generous) as writer:
        writer.write_row(qaos_row(large))
    strict = ProcessingLimits(
        max_upload_bytes=16 * 1024 * 1024,
        max_cell_bytes=100,
        max_output_bytes=16 * 1024 * 1024,
        max_image_bytes=10,
    )
    with QAOSCSVReader(target, limits=strict) as reader, pytest.raises(CSVLimitError) as error:
        next(iter(reader))
    assert error.value.code == "CSV_CELL_TOO_LARGE"
    assert error.value.details["column"] == "question_text"


def test_input_output_and_row_limits(tmp_path: Path) -> None:
    tiny = ProcessingLimits(
        max_upload_bytes=10,
        max_cell_bytes=10,
        max_output_bytes=10,
        max_image_bytes=1,
        max_rows=1,
    )
    with pytest.raises(CSVLimitError) as error:
        CSVReader(b"header\nlong value\n", limits=tiny).__enter__()
    assert error.value.code == "CSV_FILE_TOO_LARGE"
    target = tmp_path / "tiny.tsv"
    with pytest.raises(CSVLimitError), QAOSCSVWriter(target, limits=tiny):
        pass
    assert not target.exists()


def test_atomic_failure_overwrite_and_checkpoint(tmp_path: Path) -> None:
    target = tmp_path / "result.tsv"
    with pytest.raises(RuntimeError), QAOSCSVWriter(target) as writer:
        writer.write_row(qaos_row())
        raise RuntimeError("boom")
    assert not target.exists() and not list(tmp_path.glob("*.tmp"))
    with QAOSCSVWriter(target) as writer:
        writer.write_row(qaos_row())
    with pytest.raises(FileExistsError):
        QAOSCSVWriter(target).__enter__()
    checkpoint_target = tmp_path / "checkpoint.tsv"
    with (
        pytest.raises(RuntimeError),
        QAOSCSVWriter(checkpoint_target, keep_checkpoint_on_error=True) as writer,
    ):
        writer.write_row(qaos_row())
        raise RuntimeError("boom")
    assert (tmp_path / "checkpoint.tsv.checkpoint").exists()


def test_writer_rejects_input_overwrite_extra_and_oversize(tmp_path: Path) -> None:
    target = tmp_path / "same.tsv"
    with pytest.raises(FileExistsError):
        QAOSCSVWriter(target, input_path=target).__enter__()
    with pytest.raises(QAOSCommonError), QAOSCSVWriter(target) as writer:
        writer.write_row({**qaos_row(), "extra": "x"})
    assert not target.exists()
    limits = ProcessingLimits(
        max_upload_bytes=100, max_cell_bytes=10, max_output_bytes=100, max_image_bytes=1
    )
    with pytest.raises(CSVLimitError), QAOSCSVWriter(target, limits=limits) as writer:
        writer.write_row(qaos_row("too much content"))


def test_malformed_extra_fields_are_rejected() -> None:
    with CSVReader(b"a\tb\n1\t2\t3\n") as reader, pytest.raises(QAOSCommonError):
        next(iter(reader))
