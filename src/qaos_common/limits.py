"""Shared processing capacity limits."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcessingLimits:
    max_upload_bytes: int = 256 * 1024 * 1024
    max_cell_bytes: int = 64 * 1024 * 1024
    max_output_bytes: int = 512 * 1024 * 1024
    max_image_bytes: int = 20 * 1024 * 1024
    max_rows: int = 100_000
    max_images_per_row: int = 10

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.max_cell_bytes > self.max_upload_bytes:
            raise ValueError("max_cell_bytes cannot exceed max_upload_bytes")
        if self.max_image_bytes > self.max_cell_bytes:
            raise ValueError("max_image_bytes cannot exceed max_cell_bytes")


DEFAULT_LIMITS = ProcessingLimits()

__all__ = ["DEFAULT_LIMITS", "ProcessingLimits"]
