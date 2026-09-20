"""Deterministic CSV serialization profiles."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class CSVProfile:
    delimiter: str = "\t"
    encoding: str = "utf-8"
    write_bom: bool = False
    line_ending: str = "\n"
    scalar_newlines: Literal["preserve", "space"] = "preserve"
    quoting: Literal[0, 1, 2, 3] = 0  # csv.QUOTE_MINIMAL

    def __post_init__(self) -> None:
        if self.scalar_newlines not in ("preserve", "space"):
            raise ValueError("scalar_newlines must be preserve or space")
        if len(self.delimiter) != 1 or self.delimiter in "\r\n":
            raise ValueError("delimiter must be one character")
        if self.line_ending not in ("\n", "\r\n"):
            raise ValueError("line_ending must be LF or CRLF")


@dataclass(frozen=True, slots=True)
class QAOSCSVProfile(CSVProfile):
    quoting: Literal[0, 1, 2, 3] = 1
    scalar_newlines: Literal["preserve", "space"] = "space"

    def __post_init__(self) -> None:
        super(QAOSCSVProfile, self).__post_init__()
        if (
            self.delimiter != "\t"
            or self.encoding != "utf-8"
            or self.write_bom
            or self.line_ending != "\n"
            or self.quoting not in (0, 1)
        ):
            raise ValueError("QAOS requires tab, UTF-8 without BOM, LF and MINIMAL or ALL quoting")


@dataclass(frozen=True, slots=True)
class DictionaryCSVProfile(CSVProfile):
    write_bom: bool = True


__all__ = ["CSVProfile", "DictionaryCSVProfile", "QAOSCSVProfile"]
