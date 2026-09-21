import io
import os

import pytest

from qaos_common.csvio import QAOSCSVWriter


def test_failed_hard_link_keeps_existing_destination_and_removes_temporary(tmp_path, monkeypatch):
    destination = tmp_path / "output.tsv"
    original_link = os.link

    def competing_publish(source, target):
        destination.write_bytes(b"another writer")
        return original_link(source, target)

    monkeypatch.setattr(os, "link", competing_publish)
    with pytest.raises(FileExistsError), QAOSCSVWriter(destination, columns=("x",)) as writer:
        writer.write_row({"x": "value"})
    assert destination.read_bytes() == b"another writer"
    assert list(tmp_path.iterdir()) == [destination]


def test_unsupported_hard_links_fail_without_publishing_partial_output(tmp_path, monkeypatch):
    def unsupported(source, target):
        raise OSError("filesystem does not support hard links")

    monkeypatch.setattr(os, "link", unsupported)
    with pytest.raises(OSError), QAOSCSVWriter(tmp_path / "out.tsv", columns=("x",)) as writer:
        writer.write_row({"x": "value"})
    assert list(tmp_path.iterdir()) == []


def test_failed_overwrite_preserves_original_and_cleans_temporary(tmp_path, monkeypatch):
    destination = tmp_path / "output.tsv"
    destination.write_bytes(b"original")

    def denied(source, target):
        raise PermissionError("destination is open or locked")

    monkeypatch.setattr(os, "replace", denied)
    with (
        pytest.raises(PermissionError),
        QAOSCSVWriter(destination, columns=("x",), overwrite=True) as writer,
    ):
        writer.write_row({"x": "value"})
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


def test_successful_overwrite_and_checkpoint(tmp_path):
    destination = tmp_path / "output.tsv"
    destination.write_bytes(b"original")
    with QAOSCSVWriter(destination, columns=("x",), overwrite=True) as writer:
        writer.write_row({"x": "first"})
    first = destination.read_bytes()
    with (
        pytest.raises(RuntimeError),
        QAOSCSVWriter(
            destination, columns=("x",), overwrite=True, keep_checkpoint_on_error=True
        ) as writer,
    ):
        writer.write_row({"x": "second"})
        raise RuntimeError("cancelled")
    assert destination.read_bytes() == first
    assert writer.checkpoint_path.read_bytes() == b'"x"\n"second"\n'


def test_partial_binary_writes_and_stream_ownership():
    class PartialStream(io.BytesIO):
        def write(self, data):
            return super().write(data[:2])

    stream = PartialStream()
    with QAOSCSVWriter(stream, columns=("x",)) as writer:
        writer.write_row({"x": "café"})
    assert not stream.closed
    assert stream.getvalue() == '"x"\n"café"\n'.encode()
