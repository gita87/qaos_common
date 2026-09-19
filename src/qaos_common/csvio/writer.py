"""Atomic, deterministic and bounded CSV writer."""

from __future__ import annotations

import csv
import os
import tempfile
from collections.abc import Mapping, Sequence
from os import PathLike
from pathlib import Path
from typing import Any, TextIO

from qaos_common.errors import CSVLimitError, QAOSCommonError
from qaos_common.limits import DEFAULT_LIMITS, ProcessingLimits
from qaos_common.schemas.dictionary import DICTIONARY_COLUMNS
from qaos_common.schemas.qaos import QAOS_COLUMNS

from .profiles import CSVProfile, DictionaryCSVProfile, QAOSCSVProfile


class CSVWriter:
    def __init__(
        self,
        destination: str | PathLike[str],
        *,
        columns: Sequence[str],
        profile: CSVProfile | None = None,
        limits: ProcessingLimits = DEFAULT_LIMITS,
        overwrite: bool = False,
        input_path: str | PathLike[str] | None = None,
        keep_checkpoint_on_error: bool = False,
    ) -> None:
        self.destination = Path(destination)
        self.columns = tuple(columns)
        self.profile = profile or CSVProfile()
        self.limits = limits
        self.overwrite = overwrite
        self.input_path = Path(input_path) if input_path is not None else None
        self.keep_checkpoint_on_error = keep_checkpoint_on_error
        self.checkpoint_path: Path | None = None
        self._stream: TextIO | None = None
        self._writer: csv.DictWriter[str] | None = None
        self._temporary_path: Path | None = None
        self._rows_written = 0

    def __enter__(self) -> CSVWriter:
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("columns must be non-empty and unique")
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
        encoding = "utf-8-sig" if self.profile.write_bom else self.profile.encoding
        self._stream = os.fdopen(descriptor, "w", encoding=encoding, newline="")
        self._writer = csv.DictWriter(
            self._stream,
            fieldnames=self.columns,
            delimiter=self.profile.delimiter,
            lineterminator=self.profile.line_ending,
            quoting=self.profile.quoting,
            extrasaction="raise",
        )
        self._writer.writeheader()
        self._enforce_output_size()
        return self

    def write_row(self, row: Mapping[str, Any]) -> None:
        if self._writer is None:
            raise RuntimeError("Use CSVWriter as a context manager")
        if self._rows_written >= self.limits.max_rows:
            raise CSVLimitError(
                "CSV has more rows than the configured limit",
                code="CSV_OUTPUT_TOO_LARGE",
                details={"limit": self.limits.max_rows},
            )
        normalized: dict[str, str] = {}
        for column in self.columns:
            value = row.get(column, "")
            cell = "" if value is None else str(value)
            size = len(cell.encode("utf-8"))
            if size > self.limits.max_cell_bytes:
                raise CSVLimitError(
                    "CSV cell exceeds the configured limit",
                    code="CSV_CELL_TOO_LARGE",
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
                details={"row_number": self._rows_written + 2, "extra": extra},
            )
        self._writer.writerow(normalized)
        self._rows_written += 1
        self._enforce_output_size()

    def _enforce_output_size(self) -> None:
        assert self._stream is not None
        self._stream.flush()
        size = self._stream.buffer.tell()
        if size > self.limits.max_output_bytes:
            raise CSVLimitError(
                "CSV output exceeds the configured limit",
                code="CSV_OUTPUT_TOO_LARGE",
                details={"size": size, "limit": self.limits.max_output_bytes},
            )

    def _abort(self) -> None:
        if self._stream is not None and not self._stream.closed:
            self._stream.close()
        if self._temporary_path is not None and self._temporary_path.exists():
            if self.keep_checkpoint_on_error:
                checkpoint = self.destination.with_suffix(self.destination.suffix + ".checkpoint")
                os.replace(self._temporary_path, checkpoint)
                self.checkpoint_path = checkpoint
            else:
                self._temporary_path.unlink()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is not None:
            self._abort()
            return
        assert self._stream is not None and self._temporary_path is not None
        try:
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._stream.close()
            if self.destination.exists() and not self.overwrite:
                raise FileExistsError(f"Destination already exists: {self.destination}")
            os.replace(self._temporary_path, self.destination)
            self._temporary_path = None
        except BaseException:
            self._abort()
            raise


class QAOSCSVWriter(CSVWriter):
    def __init__(
        self,
        destination: str | PathLike[str],
        *,
        columns: Sequence[str] = QAOS_COLUMNS,
        limits: ProcessingLimits = DEFAULT_LIMITS,
        overwrite: bool = False,
        input_path: str | PathLike[str] | None = None,
        keep_checkpoint_on_error: bool = False,
    ) -> None:
        super().__init__(
            destination,
            columns=columns,
            profile=QAOSCSVProfile(),
            limits=limits,
            overwrite=overwrite,
            input_path=input_path,
            keep_checkpoint_on_error=keep_checkpoint_on_error,
        )


class DictionaryCSVWriter(CSVWriter):
    def __init__(
        self,
        destination: str | PathLike[str],
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


__all__ = ["CSVWriter", "DictionaryCSVWriter", "QAOSCSVWriter"]
