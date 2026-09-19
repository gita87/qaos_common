"""Progress event contract shared by QAOS applications."""

from dataclasses import dataclass

PROGRESS_STAGES = (
    "validating",
    "reading",
    "parsing",
    "tagging",
    "scoring",
    "generating",
    "converting_image",
    "writing",
    "exporting_docx",
    "completed",
)


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    current: int
    total: int | None = None
    message: str = ""
    row_number: int | None = None

    def __post_init__(self) -> None:
        if self.stage not in PROGRESS_STAGES:
            raise ValueError(f"Unknown progress stage: {self.stage}")
        if self.current < 0 or (self.total is not None and self.total < 0):
            raise ValueError("Progress values cannot be negative")
        if self.total is not None and self.current > self.total:
            raise ValueError("current cannot exceed total")
        if self.row_number is not None and self.row_number < 1:
            raise ValueError("row_number must be at least 1")


__all__ = ["PROGRESS_STAGES", "ProgressEvent"]
