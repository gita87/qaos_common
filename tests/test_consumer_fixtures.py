from pathlib import Path

from qaos_common.csvio import (
    DictionaryCSVProfile,
    DictionaryCSVReader,
    QAOSCSVReader,
    serialize_csv,
)
from qaos_common.rich_content import parse_cell, protect_segments
from qaos_common.schemas import (
    DICTIONARY_COLUMNS,
    QAOS_COLUMNS,
    parse_original_images,
    validate_dictionary_rows,
    validate_qaos_row,
)

FIXTURES = Path(__file__).parent / "fixtures" / "consumers"


def test_real_dictionary_output_preserves_bom_crlf_ids_and_na():
    payload = (FIXTURES / "dictionary.tsv").read_bytes()
    assert payload.startswith(b"\xef\xbb\xbf") and b"\r\n" in payload
    with DictionaryCSVReader(payload) as reader:
        assert reader.headers == DICTIONARY_COLUMNS
        rows = [row for _, row in reader]
    validate_dictionary_rows(rows)
    assert rows[0]["unique_id"] == "'0001" and rows[0]["image"] == "NA"
    assert (
        serialize_csv(
            rows, columns=DICTIONARY_COLUMNS, profile=DictionaryCSVProfile(line_ending="\r\n")
        )
        == payload
    )


def test_real_tagger_output_preserves_rich_content_arrays_and_provenance():
    payload = (FIXTURES / "tagged.tsv").read_bytes()
    with QAOSCSVReader(payload) as reader:
        assert reader.headers == QAOS_COLUMNS
        rows = [row for _, row in reader]
    assert len(rows) == 1
    row = rows[0]
    validate_qaos_row(row, row_number=2)
    parsed = parse_cell(row["question_text"])
    assert parsed.contains_dictionary_tag and parsed.contains_image
    assert "apple" in parsed.plain_text and "café" in parsed.plain_text
    protected = protect_segments(row["question_text"])
    assert protected.restore() == row["question_text"]
    assert "apple" not in protected.text
    provenance = parse_original_images(row["original_image"])
    assert provenance[0]["original_data_uri"] in row["question_text"]
    with QAOSCSVReader(serialize_csv(rows)) as reader:
        assert [row for _, row in reader] == rows
