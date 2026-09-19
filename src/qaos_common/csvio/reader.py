"""Streaming and bounded delimited-file reader."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from contextlib import suppress
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.limits import DEFAULT_LIMITS, ProcessingLimits

from .profiles import CSVProfile, DictionaryCSVProfile, QAOSCSVProfile

InputSource = str | PathLike[str] | bytes | bytearray | BinaryIO | TextIO


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
        self._previous_field_limit: int | None = None
        self._rows_read = 0
        self._external_wrapper: io.TextIOWrapper | None = None

    def __enter__(self) -> CSVReader:
        self._open()
        return self

    def _open(self) -> None:
        if self._reader is not None:
            raise RuntimeError("Reader is already open")
        stream: TextIO
        if isinstance(self.source, (str, PathLike)):
            path = Path(self.source)
            size = path.stat().st_size
            self._enforce_upload_size(size)
            binary = path.open("rb")
            self._owned_streams.append(binary)
            stream = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
            self._owned_streams.append(stream)
        elif isinstance(self.source, (bytes, bytearray)):
            raw = bytes(self.source)
            self._enforce_upload_size(len(raw))
            bytes_stream: BinaryIO = io.BytesIO(raw)
            stream = io.TextIOWrapper(bytes_stream, encoding="utf-8-sig", newline="")
            self._owned_streams.extend((bytes_stream, stream))
        elif isinstance(self.source, io.TextIOBase) or isinstance(self.source.read(0), str):
            stream = self.source  # type: ignore[assignment]
        else:
            binary = self.source  # type: ignore[assignment]
            stream = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
            self._external_wrapper = stream

        self._text_stream = stream
        self._previous_field_limit = csv.field_size_limit()
        # Keep csv's parser ceiling explicit while allowing the post-parse byte check
        # below to identify the exact offending column (csv itself only reports a row).
        csv.field_size_limit(self.limits.max_upload_bytes)
        try:
            reader = csv.DictReader(stream, delimiter=self.profile.delimiter)
            raw_headers = list(reader.fieldnames) if reader.fieldnames is not None else None
        except (csv.Error, UnicodeError) as exc:
            self.close()
            raise QAOSCommonError(
                "Could not read the CSV header",
                code="QAOS_SCHEMA_INVALID",
                details={"row_number": 1},
            ) from exc
        if raw_headers is None:
            self.close()
            raise QAOSCommonError("CSV is empty", code="QAOS_SCHEMA_INVALID")
        raw_headers[0] = raw_headers[0].removeprefix("\ufeff")
        self.headers = tuple(raw_headers)
        self._reader = reader

    def _enforce_upload_size(self, size: int) -> None:
        if size > self.limits.max_upload_bytes:
            raise CSVLimitError(
                "CSV input exceeds the configured upload limit",
                code="CSV_FILE_TOO_LARGE",
                details={"size": size, "limit": self.limits.max_upload_bytes},
            )

    def __iter__(self) -> Iterator[tuple[int, dict[str, str]]]:
        if self._reader is None:
            raise RuntimeError("Use CSVReader as a context manager")
        while True:
            try:
                row = next(self._reader)
            except StopIteration:
                return
            except (csv.Error, UnicodeError) as exc:
                row_number = self._reader.line_num
                raise QAOSCommonError(
                    "CSV row could not be parsed",
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
                    details={"row_number": row_number, "limit": self.limits.max_rows},
                )
            if None in row:
                raise QAOSCommonError(
                    "CSV row contains more fields than its header",
                    code="QAOS_SCHEMA_INVALID",
                    details={"row_number": row_number},
                )
            cleaned: dict[str, str] = {}
            for column, value in row.items():
                cell = "" if value is None else value
                size = len(cell.encode("utf-8"))
                if size > self.limits.max_cell_bytes:
                    raise CSVLimitError(
                        "CSV cell exceeds the configured limit",
                        code="CSV_CELL_TOO_LARGE",
                        details={
                            "row_number": row_number,
                            "column": column,
                            "size": size,
                            "limit": self.limits.max_cell_bytes,
                        },
                    )
                cleaned[column] = cell
            yield row_number, cleaned

    def close(self) -> None:
        if self._previous_field_limit is not None:
            csv.field_size_limit(self._previous_field_limit)
            self._previous_field_limit = None
        for stream in reversed(self._owned_streams):
            with suppress(OSError, ValueError):
                stream.close()
        self._owned_streams.clear()
        if self._external_wrapper is not None:
            with suppress(OSError, ValueError):
                self._external_wrapper.detach()
            self._external_wrapper = None
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
