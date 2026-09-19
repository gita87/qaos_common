import json

import pytest

from qaos_common.errors import OriginalImageError
from qaos_common.rich_content import build_data_uri
from qaos_common.schemas.original_image import (
    append_original_image,
    parse_original_images,
    serialize_original_images,
)

PNG = b"\x89PNG\r\n\x1a\nminimal"


def record(index: int = 0) -> dict[str, object]:
    return {
        "column": "question_text",
        "index": index,
        "original_mime": "image/png",
        "original_data_uri": build_data_uri(PNG, "image/png"),
    }


def test_canonical_single_and_legacy_parsing() -> None:
    canonical = serialize_original_images([record()])
    assert canonical.startswith('[{"column":')
    assert parse_original_images(canonical)[0]["index"] == 0
    assert len(parse_original_images(json.dumps(record()))) == 1
    assert len(parse_original_images(repr(record()))) == 1
    assert parse_original_images("") == []


def test_append_preserves_existing_records() -> None:
    value = append_original_image(None, record())
    value = append_original_image(value, record(1))
    assert [item["index"] for item in parse_original_images(value)] == [0, 1]


@pytest.mark.parametrize("value", ["__import__('os').system('bad')", "42", "[{}]"])
def test_invalid_legacy_input_is_safe(value: str) -> None:
    with pytest.raises(OriginalImageError) as error:
        parse_original_images(value)
    assert "minimal" not in str(error.value)


def test_mime_disagreement_is_rejected() -> None:
    bad = record()
    bad["original_mime"] = "image/jpeg"
    with pytest.raises(OriginalImageError):
        serialize_original_images([bad])
