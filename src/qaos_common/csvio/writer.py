"""Atomic, deterministic and bounded CSV writer."""

from __future__ import annotations

import codecs
import csv
import io
import json
import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO

from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.limits import DEFAULT_LIMITS, ProcessingLimits
from qaos_common.schemas.dictionary import DICTIONARY_COLUMNS
from qaos_common.schemas.original_image import parse_original_images
from qaos_common.schemas.qaos import ARRAY_COLUMNS, QAOS_COLUMNS, serialize_array

from .profiles import CSVProfile, DictionaryCSVProfile, QAOSCSVProfile


class CSVWriter:
    def __init__(
        self,
        destination: str | PathLike[str] | BinaryIO,
        *,
        columns: Sequence[str],
        profile: CSVProfile | None = None,
        limits: ProcessingLimits = DEFAULT_LIMITS,
        overwrite: bool = False,
        input_path: str | PathLike[str] | None = None,
        keep_checkpoint_on_error: bool = False,
    ) -> None:
        self.destination = Path(destination) if isinstance(destination, (str, PathLike)) else None
        self._external = destination if self.destination is None else None
        self.columns = tuple(columns)
        self.profile = profile or CSVProfile()
        self.limits = limits
        self.overwrite = overwrite
        self.input_path = Path(input_path) if input_path is not None else None
        self.keep_checkpoint_on_error = keep_checkpoint_on_error
        self.checkpoint_path: Path | None = None
        self._stream: BinaryIO | None = None
        self._bytes_written = 0
        self._encoder = codecs.getincrementalencoder(self.profile.encoding)()
        self._entered = False
        self._temporary_path: Path | None = None
        self._rows_written = 0

    def __enter__(self) -> CSVWriter:
        if self._entered:
            raise RuntimeError("CSVWriter instances are single-use")
        self._entered = True
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("columns must be non-empty and unique")
        if self.destination is None:
            self._stream = self._external  # type: ignore[assignment]
        else:
            destination = self.destination.resolve()
            if (
                self.input_path is not None
                and destination == self.input_path.resolve()
                and not self.overwrite
            ):
                raise FileExistsError("Refusing to overwrite the input file")
            if self.destination.exists() and not self.overwrite:
                raise FileExistsError(f"Destination already exists: {self.destination}")
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{self.destination.name}.", suffix=".tmp", dir=self.destination.parent
            )
            self._temporary_path = Path(temporary)
            self._stream = os.fdopen(descriptor, "wb")
        try:
            if self.profile.write_bom:
                self._write_bytes(b"\xef\xbb\xbf")
            self._emit(self.columns)
        except BaseException:
            self._abort()
            raise
        return self

    def write_row(self, row: Mapping[str, Any]) -> None:
        if self._stream is None:
            raise RuntimeError("Use CSVWriter as a context manager")
        if self._rows_written >= self.limits.max_rows:
            raise CSVLimitError(
                "CSV has more rows than the configured limit",
                code="CSV_OUTPUT_TOO_LARGE",
                stage="writing",
                details={"limit": self.limits.max_rows},
            )
        normalized: dict[str, str] = {}
        for column in self.columns:
            value = row.get(column, "")
            if isinstance(self.profile, QAOSCSVProfile) and column in ARRAY_COLUMNS:
                try:
                    cell = serialize_array(value)
                except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                    raise QAOSCommonError(
                        "Invalid QAOS array cell",
                        code="QAOS_SCHEMA_INVALID",
                        stage="writing",
                        details={"row_number": self._rows_written + 2, "column": column},
                    ) from exc
            elif isinstance(self.profile, QAOSCSVProfile) and column == "original_image":
                try:
                    cell = json.dumps(
                        parse_original_images(value),
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    )
                except (
                    QAOSCommonError,
                    TypeError,
                    ValueError,
                    OverflowError,
                    RecursionError,
                ) as exc:
                    raise QAOSCommonError(
                        "Invalid QAOS original_image cell",
                        code="QAOS_SCHEMA_INVALID",
                        stage="writing",
                        details={"row_number": self._rows_written + 2, "column": column},
                    ) from exc
            else:
                cell = "" if value is None else str(value)
                if self.profile.scalar_newlines == "space":
                    cell = cell.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
            size = len(cell.encode("utf-8"))
            if size > self.limits.max_cell_bytes:
                raise CSVLimitError(
                    "CSV cell exceeds the configured limit",
                    code="CSV_CELL_TOO_LARGE",
                    stage="writing",
                    details={
                        "row_number": self._rows_written + 2,
                        "column": column,
                        "size": size,
                        "limit": self.limits.max_cell_bytes,
                    },
                )
            normalized[column] = cell
        extra = tuple(key for key in row if key not in self.columns)
        if extra:
            raise QAOSCommonError(
                "Row contains columns that are not in the writer schema",
                code="QAOS_SCHEMA_INVALID",
                stage="writing",
                details={"row_number": self._rows_written + 2, "extra": extra},
            )
        self._emit([normalized[column] for column in self.columns])
        self._rows_written += 1

    def _emit(self, values: Sequence[str]) -> None:
        for value in values:
            if len(value.encode("utf-8")) > self.limits.max_cell_bytes:
                raise CSVLimitError(
                    "CSV cell exceeds the configured limit",
                    code="CSV_CELL_TOO_LARGE",
                    stage="writing",
                )
        buffer = io.StringIO(newline="")
        csv.writer(
            buffer,
            delimiter=self.profile.delimiter,
            lineterminator="\r\n",
            quoting=self.profile.quoting,
        ).writerow(values)
        text = buffer.getvalue()[:-2] + self.profile.line_ending
        self._write_bytes(self._encoder.encode(text))

    def _write_bytes(self, payload: bytes) -> None:
        assert self._stream is not None
        size = self._bytes_written + len(payload)
        if size > self.limits.max_output_bytes:
            raise CSVLimitError(
                "CSV output exceeds the configured limit",
                code="CSV_OUTPUT_TOO_LARGE",
                stage="writing",
                details={"size": size, "limit": self.limits.max_output_bytes},
            )
        view = memoryview(payload)
        while view:
            written = self._stream.write(view)
            if written is None or written <= 0:
                raise OSError("CSV stream did not accept output")
            view = view[written:]
        self._bytes_written = size

    def _abort(self) -> None:
        if self.destination is not None and self._stream is not None and not self._stream.closed:
            self._stream.close()
        if self._temporary_path is not None and self._temporary_path.exists():
            if self.keep_checkpoint_on_error:
                assert self.destination is not None
                checkpoint = self.destination.with_suffix(self.destination.suffix + ".checkpoint")
                os.replace(self._temporary_path, checkpoint)
                self.checkpoint_path = checkpoint
            else:
                self._temporary_path.unlink()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None:
            self._abort()
            return
        if self.destination is None:
            self._stream = None
            return
        assert self._stream is not None and self._temporary_path is not None
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
            if self.destination.exists() and not self.overwrite:
                raise FileExistsError(f"Destination already exists: {self.destination}")
            if self.overwrite:
                os.replace(self._temporary_path, self.destination)
            else:
                os.link(self._temporary_path, self.destination)
                self._temporary_path.unlink()
            self._temporary_path = None
        except BaseException:
            self._abort()
            raise


class QAOSCSVWriter(CSVWriter):
    def __init__(
        self,
        destination: str | PathLike[str] | BinaryIO,
        *,
        columns: Sequence[str] = QAOS_COLUMNS,
        profile: QAOSCSVProfile | None = None,
        limits: ProcessingLimits = DEFAULT_LIMITS,
        overwrite: bool = False,
        input_path: str | PathLike[str] | None = None,
        keep_checkpoint_on_error: bool = False,
    ) -> None:
        super().__init__(
            destination,
            columns=columns,
            profile=profile or QAOSCSVProfile(),
            limits=limits,
            overwrite=overwrite,
            input_path=input_path,
            keep_checkpoint_on_error=keep_checkpoint_on_error,
        )


class DictionaryCSVWriter(CSVWriter):
    def __init__(
        self,
        destination: str | PathLike[str] | BinaryIO,
        *,
        columns: Sequence[str] = DICTIONARY_COLUMNS,
        profile: DictionaryCSVProfile | None = None,
        limits: ProcessingLimits = DEFAULT_LIMITS,
        overwrite: bool = False,
        input_path: str | PathLike[str] | None = None,
    ) -> None:
        super().__init__(
            destination,
            columns=columns,
            profile=profile or DictionaryCSVProfile(),
            limits=limits,
            overwrite=overwrite,
            input_path=input_path,
        )


__all__ = ["CSVWriter", "DictionaryCSVWriter", "QAOSCSVWriter", "serialize_csv"]


def serialize_csv(
    rows: Iterable[Mapping[str, Any]],
    *,
    columns: Sequence[str] = QAOS_COLUMNS,
    profile: CSVProfile | None = None,
    limits: ProcessingLimits = DEFAULT_LIMITS,
) -> bytes:
    """Serialize to bytes with the same guards as path and binary-stream output."""
    stream = io.BytesIO()
    with CSVWriter(
        stream, columns=columns, profile=profile or QAOSCSVProfile(), limits=limits
    ) as writer:
        for row in rows:
            writer.write_row(row)
    return stream.getvalue()
