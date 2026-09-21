"""Streaming and bounded delimited-file reader."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from os import PathLike
from pathlib import Path
from threading import RLock
from typing import Any, BinaryIO, TextIO

from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.limits import DEFAULT_LIMITS, ProcessingLimits

from .profiles import CSVProfile, DictionaryCSVProfile, QAOSCSVProfile

InputSource = str | PathLike[str] | bytes | bytearray | BinaryIO | TextIO

_FIELD_LIMIT_LOCK = RLock()


@contextmanager
def _parser_limit(limit: int) -> Iterator[None]:
    # Lock only a parser operation, never a reader lifetime or a yielded row.
    # Nested readers and readers closed in any order cannot restore stale limits.
    with _FIELD_LIMIT_LOCK:
        previous = csv.field_size_limit()
        csv.field_size_limit(limit)
        try:
            yield
        finally:
            csv.field_size_limit(previous)


def _check_upload_size(size: int, limit: int) -> None:
    if size > limit:
        raise CSVLimitError(
            "CSV input exceeds the configured upload limit",
            code="CSV_FILE_TOO_LARGE",
            stage="reading",
            details={"size": size, "limit": limit},
        )


class _BoundedBinary(io.RawIOBase):
    """Read at most the budget plus one byte; never close the caller's stream."""

    def __init__(self, source: BinaryIO, limit: int) -> None:
        self.source = source
        self.limit = limit
        self.size = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        data = self.source.read(min(len(buffer), max(1, self.limit - self.size + 1)))
        if data is None:
            raise BlockingIOError("CSV input requires a blocking binary stream")
        self.size += len(data)
        _check_upload_size(self.size, self.limit)
        buffer[: len(data)] = data
        return len(data)


class _BoundedTextLines:
    """Count UTF-8 bytes of supplied text, including BOM and line separators."""

    def __init__(self, source: TextIO, limit: int) -> None:
        self.source = source
        self.limit = limit
        self.size = 0

    def __iter__(self) -> _BoundedTextLines:
        return self

    def __next__(self) -> str:
        line = self.source.readline(max(1, self.limit - self.size + 1))
        if not line:
            raise StopIteration
        self.size += len(line.encode("utf-8"))
        _check_upload_size(self.size, self.limit)
        return line


class CSVReader:
    """Yield ``(physical_row_number, row_mapping)`` without materializing the file."""

    def __init__(
        self,
        source: InputSource,
        *,
        profile: CSVProfile | None = None,
        limits: ProcessingLimits = DEFAULT_LIMITS,
    ) -> None:
        self.source = source
        self.profile = profile or CSVProfile()
        self.limits = limits
        self.headers: tuple[str, ...] = ()
        self._text_stream: TextIO | None = None
        self._owned_streams: list[Any] = []
        self._reader: csv.DictReader[str] | None = None
        self._rows_read = 0

    def __enter__(self) -> CSVReader:
        if self._reader is not None:
            raise RuntimeError("Reader is already open")
        try:
            self._open()
        except BaseException:
            self.close()
            raise
        return self

    def _open(self) -> None:
        self._rows_read = 0
        self.headers = ()
        stream: TextIO
        binary: BinaryIO | None = None
        if isinstance(self.source, (str, PathLike)):
            path = Path(self.source)
            size = path.stat().st_size
            _check_upload_size(size, self.limits.max_upload_bytes)
            binary = path.open("rb")
            self._owned_streams.append(binary)
        elif isinstance(self.source, (bytes, bytearray)):
            raw = bytes(self.source)
            _check_upload_size(len(raw), self.limits.max_upload_bytes)
            binary = io.BytesIO(raw)
            self._owned_streams.append(binary)
        elif isinstance(self.source, io.TextIOBase) or isinstance(self.source.read(0), str):
            stream = self.source  # type: ignore[assignment]
        else:
            binary = self.source  # type: ignore[assignment]

        if binary is not None:
            bounded = _BoundedBinary(binary, self.limits.max_upload_bytes)
            buffered = io.BufferedReader(bounded)
            stream = io.TextIOWrapper(buffered, encoding="utf-8-sig", newline="")
            self._owned_streams.extend((bounded, buffered, stream))

        self._text_stream = stream
        try:
            reader = csv.DictReader(
                _BoundedTextLines(stream, self.limits.max_upload_bytes),
                delimiter=self.profile.delimiter,
                strict=True,
            )
            with _parser_limit(self.limits.max_upload_bytes):
                raw_headers = list(reader.fieldnames) if reader.fieldnames is not None else None
        except (csv.Error, UnicodeError) as exc:
            raise QAOSCommonError(
                "Could not read the CSV header",
                code="QAOS_SCHEMA_INVALID",
                stage="reading",
                details={"row_number": 1},
            ) from exc
        if not raw_headers:
            raise QAOSCommonError("CSV is empty", code="QAOS_SCHEMA_INVALID", stage="reading")
        raw_headers[0] = raw_headers[0].removeprefix("\ufeff")
        if any(not name.strip() for name in raw_headers) or len(set(raw_headers)) != len(
            raw_headers
        ):
            raise QAOSCommonError(
                "CSV headers must be non-empty and unique",
                code="QAOS_SCHEMA_INVALID",
                stage="reading",
                details={"row_number": 1},
            )
        for column in raw_headers:
            self._check_cell(column, column=column, row_number=1)
        reader.fieldnames = raw_headers
        self.headers = tuple(raw_headers)
        self._reader = reader

    def _check_cell(self, cell: str, *, column: str, row_number: int) -> None:
        size = len(cell.encode("utf-8"))
        if size > self.limits.max_cell_bytes:
            raise CSVLimitError(
                "CSV cell exceeds the configured limit",
                code="CSV_CELL_TOO_LARGE",
                stage="reading",
                details={
                    "row_number": row_number,
                    "column": column,
                    "size": size,
                    "limit": self.limits.max_cell_bytes,
                },
            )

    def __iter__(self) -> Iterator[tuple[int, dict[str, str]]]:
        if self._reader is None:
            raise RuntimeError("Use CSVReader as a context manager")
        while True:
            try:
                with _parser_limit(self.limits.max_upload_bytes):
                    row = next(self._reader)
            except StopIteration:
                return
            except (csv.Error, UnicodeError) as exc:
                row_number = self._reader.line_num
                raise QAOSCommonError(
                    "CSV row could not be parsed",
                    stage="reading",
                    code=(
                        "CSV_CELL_TOO_LARGE"
                        if "field larger" in str(exc)
                        else "QAOS_SCHEMA_INVALID"
                    ),
                    details={"row_number": row_number},
                ) from exc
            self._rows_read += 1
            row_number = self._reader.line_num
            if self._rows_read > self.limits.max_rows:
                raise CSVLimitError(
                    "CSV has more rows than the configured limit",
                    code="CSV_FILE_TOO_LARGE",
                    stage="reading",
                    details={"row_number": row_number, "limit": self.limits.max_rows},
                )
            if None in row:
                raise QAOSCommonError(
                    "CSV row contains more fields than its header",
                    code="QAOS_SCHEMA_INVALID",
                    stage="reading",
                    details={"row_number": row_number},
                )
            cleaned: dict[str, str] = {}
            for column, value in row.items():
                cell = "" if value is None else value
                self._check_cell(cell, column=column, row_number=row_number)
                cleaned[column] = cell
            yield row_number, cleaned

    def close(self) -> None:
        for stream in reversed(self._owned_streams):
            with suppress(OSError, ValueError):
                stream.close()
        self._owned_streams.clear()
        self._text_stream = None
        self._reader = None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


class QAOSCSVReader(CSVReader):
    def __init__(self, source: InputSource, *, limits: ProcessingLimits = DEFAULT_LIMITS) -> None:
        super().__init__(source, profile=QAOSCSVProfile(), limits=limits)


class DictionaryCSVReader(CSVReader):
    def __init__(self, source: InputSource, *, limits: ProcessingLimits = DEFAULT_LIMITS) -> None:
        super().__init__(source, profile=DictionaryCSVProfile(), limits=limits)


__all__ = ["CSVReader", "DictionaryCSVReader", "InputSource", "QAOSCSVReader"]
