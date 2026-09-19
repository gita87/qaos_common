"""Deterministic CSV serialization profiles."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class CSVProfile:
    delimiter: str = "\t"
    encoding: str = "utf-8"
    write_bom: bool = False
    line_ending: str = "\n"
    quoting: Literal[0, 1, 2, 3] = 0  # csv.QUOTE_MINIMAL

    def __post_init__(self) -> None:
        if len(self.delimiter) != 1:
            raise ValueError("delimiter must be one character")
        if self.line_ending not in ("\n", "\r\n"):
            raise ValueError("line_ending must be LF or CRLF")


@dataclass(frozen=True, slots=True)
class QAOSCSVProfile(CSVProfile):
    pass


@dataclass(frozen=True, slots=True)
class DictionaryCSVProfile(CSVProfile):
    write_bom: bool = True


__all__ = ["CSVProfile", "DictionaryCSVProfile", "QAOSCSVProfile"]
