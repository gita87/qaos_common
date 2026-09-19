"""The versioned QAOS 1.0 tabular contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from qaos_common.errors import SchemaValidationError

QAOS_SCHEMA_VERSION = "qaos/1.0"
QAOS_COLUMNS = (
    "question_number",
    "question_text",
    "option_a",
    "option_a_image",
    "option_b",
    "option_b_image",
    "option_c",
    "option_c_image",
    "option_d",
    "option_d_image",
    "option_e",
    "option_e_image",
    "option_f",
    "option_f_image",
    "option_g",
    "option_g_image",
    "option_h",
    "option_h_image",
    "option_i",
    "option_i_image",
    "answer",
    "explanation",
    "flip_front",
    "flip_back",
    "train",
    "original_image",
)
NON_GENERATION_COLUMNS = frozenset(
    {"question_number", "answer", "flip_front", "flip_back", "train", "original_image"}
)
OPTION_IMAGE_MAP = {f"option_{letter}": f"option_{letter}_image" for letter in "abcdefghi"}

ValidationMode = Literal["strict", "compatible"]


@dataclass(frozen=True, slots=True)
class HeaderValidationResult:
    columns: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    duplicates: tuple[str, ...]
    order_valid: bool

    @property
    def valid(self) -> bool:
        return not self.missing and not self.duplicates and self.order_valid


def _validate_headers(
    headers: Sequence[str], expected: Sequence[str], mode: ValidationMode, code: str
) -> HeaderValidationResult:
    if mode not in ("strict", "compatible"):
        raise ValueError("mode must be 'strict' or 'compatible'")
    actual = tuple(headers)
    seen: set[str] = set()
    duplicate_items: list[str] = []
    for item in actual:
        if item in seen:
            duplicate_items.append(item)
        else:
            seen.add(item)
    duplicates = tuple(duplicate_items)
    missing = tuple(item for item in expected if item not in actual)
    extra = tuple(item for item in actual if item not in expected)
    expected_present = tuple(item for item in actual if item in expected)
    order_valid = expected_present == tuple(expected) if not missing else False
    result = HeaderValidationResult(actual, missing, extra, duplicates, order_valid)
    invalid = bool(missing or duplicates or not order_valid or (mode == "strict" and extra))
    if invalid:
        raise SchemaValidationError(
            "CSV headers do not satisfy the schema contract",
            code=code,
            details={
                "missing": missing,
                "extra": extra,
                "duplicates": duplicates,
                "order_valid": order_valid,
                "mode": mode,
            },
        )
    return result


def validate_qaos_headers(
    headers: Sequence[str], mode: ValidationMode = "strict"
) -> HeaderValidationResult:
    """Validate names/order; compatible mode permits reported extra columns."""
    return _validate_headers(headers, QAOS_COLUMNS, mode, "QAOS_SCHEMA_INVALID")


def validate_qaos_row(row: Mapping[str, Any], *, row_number: int | None = None) -> None:
    missing = tuple(column for column in QAOS_COLUMNS if column not in row)
    if missing:
        raise SchemaValidationError(
            "QAOS row is missing required columns",
            code="QAOS_SCHEMA_INVALID",
            details={"row_number": row_number, "missing": missing},
        )


__all__ = [
    "NON_GENERATION_COLUMNS",
    "OPTION_IMAGE_MAP",
    "QAOS_COLUMNS",
    "QAOS_SCHEMA_VERSION",
    "HeaderValidationResult",
    "ValidationMode",
    "validate_qaos_headers",
    "validate_qaos_row",
]
