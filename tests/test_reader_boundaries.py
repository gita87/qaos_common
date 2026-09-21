from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from qaos_common import ProcessingLimits
from qaos_common.csvio import CSVReader
from qaos_common.errors import CSVLimitError, QAOSCommonError


def limits(upload: int, cell: int | None = None) -> ProcessingLimits:
    return ProcessingLimits(
        max_upload_bytes=upload,
        max_cell_bytes=cell or upload,
        max_image_bytes=1,
        max_output_bytes=upload,
    )


@pytest.mark.parametrize("kind", ["path", "bytes", "bytearray", "binary", "text"])
@pytest.mark.parametrize("extra", [0, 1])
def test_all_sources_enforce_the_same_utf8_budget(tmp_path, kind, extra):
    payload = '\ufeffx\r\n"é\n終"\r\n'.encode()
    path = tmp_path / "input.tsv"
    path.write_bytes(payload)
    sources = {
        "path": path,
        "bytes": payload,
        "bytearray": bytearray(payload),
        "binary": io.BytesIO(payload),
        "text": io.StringIO(payload.decode(), newline=""),
    }
    source = sources[kind]
    original_limit = csv.field_size_limit()
    if extra:
        with (
            pytest.raises(CSVLimitError) as caught,
            CSVReader(source, limits=limits(len(payload) - extra)) as reader,
        ):
            list(reader)
        assert caught.value.code == "CSV_FILE_TOO_LARGE"
        assert caught.value.stage == "reading"
    else:
        with CSVReader(source, limits=limits(len(payload))) as reader:
            assert list(reader) == [(3, {"x": "é\n終"})]
    assert csv.field_size_limit() == original_limit
    if kind in ("binary", "text"):
        assert not source.closed


class NonSeekable:
    def __init__(self, value: bytes):
        self.source = io.BytesIO(value)
        self.requests = []

    def read(self, size):
        assert size >= 0, "must never perform an unbounded read"
        self.requests.append(size)
        return self.source.read(size)


def test_nonseekable_upload_cannot_read_past_budget_plus_one():
    source = NonSeekable(b"x\n" + b"a" * 1_000_000)
    with pytest.raises(CSVLimitError), CSVReader(source, limits=limits(32)) as reader:
        list(reader)
    assert source.source.tell() == 33
    assert max(source.requests) <= 33
    assert not source.source.closed


def test_text_reader_stops_before_allocating_an_unbounded_line():
    source = io.StringIO("x\n" + "終" * 1_000_000, newline="")
    with pytest.raises(CSVLimitError), CSVReader(source, limits=limits(32)) as reader:
        list(reader)
    assert source.tell() <= 33
    assert not source.closed


def test_stream_budget_includes_blank_lines_and_header():
    source = io.StringIO("x\n" + "\n" * 20)
    with pytest.raises(CSVLimitError), CSVReader(source, limits=limits(8)) as reader:
        list(reader)


@pytest.mark.parametrize("payload", [b"\xff", b'"unfinished', b"a\ta\n", b"\n", b"a\t\n"])
def test_failed_enter_leaves_external_stream_open_and_restores_parser_limit(payload):
    source = io.BytesIO(payload)
    before = csv.field_size_limit()
    with pytest.raises(QAOSCommonError):
        CSVReader(source).__enter__()
    assert not source.closed
    assert csv.field_size_limit() == before


def test_header_cell_budget_is_enforced():
    with (
        pytest.raises(CSVLimitError) as caught,
        CSVReader(b"long_header\nx\n", limits=limits(30, cell=4)),
    ):
        pass
    assert caught.value.details["row_number"] == 1


def test_nested_readers_and_non_lifo_close_do_not_change_global_limit():
    before = csv.field_size_limit()
    big = CSVReader(b"x\n" + b"a" * 200_000 + b"\n", limits=limits(300_000))
    small = CSVReader(b"x\nb\n", limits=limits(8))
    try:
        big.__enter__()
        small.__enter__()
        assert csv.field_size_limit() == before
        assert len(next(iter(big))[1]["x"]) == 200_000
        big.close()
        assert list(small) == [(2, {"x": "b"})]
    finally:
        big.close()
        small.close()
    assert csv.field_size_limit() == before


def test_concurrent_readers_keep_independent_limits_without_lifetime_lock():
    barrier = Barrier(2)
    before = csv.field_size_limit()

    def read(value, upload):
        with CSVReader(io.BytesIO(value), limits=limits(upload)) as reader:
            barrier.wait(timeout=5)
            return list(reader)

    with ThreadPoolExecutor(max_workers=2) as executor:
        large = executor.submit(read, b"x\n" + b"a" * 200_000 + b"\n", 300_000)
        small = executor.submit(read, b"x\nb\n", 8)
        assert len(large.result(timeout=10)[0][1]["x"]) == 200_000
        assert small.result(timeout=10) == [(2, {"x": "b"})]
    assert csv.field_size_limit() == before


def test_rows_and_parse_failure_restore_limit():
    before = csv.field_size_limit()
    with CSVReader(io.StringIO('x\n"unterminated')) as reader:
        with pytest.raises(QAOSCommonError):
            list(reader)
        assert csv.field_size_limit() == before


def test_file_growing_after_open_is_still_bounded(tmp_path):
    path = tmp_path / "growing.tsv"
    path.write_bytes(b"x\na\n")
    with CSVReader(path, limits=limits(8)) as reader:
        with path.open("ab") as stream:
            stream.write(b"b\n" * 20)
        with pytest.raises(CSVLimitError):
            list(reader)
