import base64
from dataclasses import replace

import pytest

from qaos_common.errors import DataURIError, ProtectedSegmentError
from qaos_common.limits import ProcessingLimits
from qaos_common.rich_content import (
    build_data_uri,
    contains_image_data_uri,
    decode_data_uri,
    find_data_uris,
    parse_cell,
    protect_segments,
    restore_segments,
    validate_image_data_uri,
)

PNG = b"\x89PNG\r\n\x1a\nminimal"
GIF = b"GIF89aminimal"


def test_data_uri_detect_validate_decode_and_build() -> None:
    uri = build_data_uri(PNG, "image/png")
    rich = f'<p style="color:red">Before<br/>{uri}</p><p>After</p>'
    assert contains_image_data_uri(rich)
    found = find_data_uris(rich)
    assert len(found) == 1
    assert "minimal" not in repr(found[0])
    assert validate_image_data_uri(uri).mime_type == "image/png"
    data, mime = decode_data_uri(uri)
    assert (data, mime) == (PNG, "image/png")


def test_whitespace_and_multiple_images() -> None:
    png = build_data_uri(PNG, "image/png").replace("base64,", "base64,\n")
    gif = build_data_uri(GIF, "image/gif")
    assert len(find_data_uris(f"<b>x</b>{png};middle;{gif}")) == 2


def test_invalid_base64_mime_and_limits_are_safe() -> None:
    with pytest.raises(DataURIError) as invalid:
        validate_image_data_uri("data:image/png;base64,not!base64")
    assert invalid.value.code == "DATA_URI_INVALID"
    mismatch = "data:image/jpeg;base64," + base64.b64encode(PNG).decode()
    with pytest.raises(DataURIError) as error:
        validate_image_data_uri(mismatch)
    assert error.value.code == "IMAGE_MIME_MISMATCH"
    limits = ProcessingLimits(
        max_upload_bytes=100, max_cell_bytes=100, max_output_bytes=100, max_image_bytes=1
    )
    with pytest.raises(DataURIError):
        decode_data_uri(build_data_uri(PNG, "image/png"), limits=limits)
    with pytest.raises(DataURIError):
        build_data_uri(b"x", "application/octet-stream")


def test_parser_handles_nested_markup_latex_and_images() -> None:
    uri = build_data_uri(PNG, "image/png")
    value = (
        '<table style="color:red"><tr><td>Alpha<ul><li>Beta<ul><li>Gamma</li></ul>'
        f'</li></ul></td><td><img src="{uri}"></td></tr></table>'
        r"Outside $x^2$ and \[y=1\]"
    )
    parsed = parse_cell(value)
    assert parsed.contains_html and parsed.contains_latex and parsed.contains_image
    assert parsed.image_count == 1
    assert "Alpha" in parsed.plain_text and "Gamma" in parsed.plain_text
    assert "base64" not in parsed.plain_text and "color:red" not in parsed.plain_text
    assert uri not in repr(parsed.protected_segments)


def test_dictionary_tag_and_empty_cell() -> None:
    parsed = parse_cell('<span class="dictionary-term">Word</span>')
    assert parsed.contains_dictionary_tag
    assert parsed.plain_text == "Word"
    assert parse_cell(None).plain_text == ""


def test_protection_restores_byte_for_byte_and_detects_tampering() -> None:
    uri = build_data_uri(PNG, "image/png")
    value = f'<p data-x="1">A $x$ <style>.x{{color:red}}</style>{uri}</p>'
    protected = protect_segments(value)
    assert protected.restore() == value
    assert uri not in repr(protected)
    missing = protected.text.replace(protected.segments[0].placeholder, "")
    with pytest.raises(ProtectedSegmentError):
        restore_segments(missing, protected.segments)
    repeated = protected.text + protected.segments[0].placeholder
    with pytest.raises(ProtectedSegmentError):
        restore_segments(repeated, protected.segments)
    with pytest.raises(ProtectedSegmentError):
        restore_segments(protected.text + "[[QAOS_PROTECTED_deadbeef_9]]", protected.segments)


def test_custom_literal_and_pattern_protection() -> None:
    protected = protect_segments(
        "one SECRET two ID-42", literal_segments=["SECRET"], patterns=[r"ID-\d+"]
    )
    assert len(protected.segments) == 2
    assert protected.restore() == "one SECRET two ID-42"


def test_parsed_cell_repr_never_exposes_payload_even_when_constructed_directly():
    uri = build_data_uri(PNG + b"PRIVATE_SENTINEL" * 8, "image/png")
    payload = uri.split(",", 1)[1]
    parsed = parse_cell(f'<p>Safe</p><img src="{uri}">')
    for candidate in (parsed, replace(parsed, plain_text=uri)):
        rendered = repr(candidate)
        assert payload not in rendered and uri not in rendered
        assert "image_count=1" in rendered
    assert parsed.original.endswith(f'<img src="{uri}">')
    assert parsed.plain_text == "Safe"


def test_tagger_dictionary_markup_and_latex_environment_are_protected():
    tagged = '<span data-dict-id="0001">apple</span>'
    latex = r"\begin{equation}apple + 1\end{equation}"
    source = f"{tagged} {latex} apple"
    protected = protect_segments(source)
    assert protected.text.count("apple") == 1
    assert protected.restore() == source
    parsed = parse_cell(source)
    assert parsed.contains_dictionary_tag and parsed.contains_latex
    assert parsed.plain_text == "apple apple"
