"""Exercise real sibling APIs without editing or installing into their projects.

Requires python-docx and Pillow in the invoking environment. The renderer subprocess
uses its own Python environment. This is an opt-in integration probe, not a common
runtime dependency or a claim that the sibling projects have been migrated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from qaos_common.csvio import (
    DictionaryCSVProfile,
    DictionaryCSVReader,
    QAOSCSVReader,
    serialize_csv,
)
from qaos_common.rich_content import build_data_uri, parse_cell, protect_segments
from qaos_common.schemas import (
    DICTIONARY_COLUMNS,
    NON_GENERATION_COLUMNS,
    QAOS_COLUMNS,
    serialize_original_images,
    validate_dictionary_rows,
    validate_qaos_headers,
    validate_qaos_row,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", type=Path, required=True)
    parser.add_argument("--renderer-python", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.projects_root / "dict_docx_to_csv_task"))
    sys.path.insert(0, str(args.projects_root / "tag_dict_to_qaos_csv"))
    from docx import Document
    from PIL import Image
    from qaos_dictionary import convert_dictionary_docx_to_csv
    from src.tagger import tag_qaos_csv

    doc = Document()
    table = doc.add_table(rows=3, cols=2)
    for cells, values in zip(
        table.rows,
        [("word", "definition"), ("apple", "fruit"), ("café", "coffee house")],
        strict=True,
    ):
        for cell, value in zip(cells.cells, values, strict=True):
            cell.text = value
    source = io.BytesIO()
    doc.save(source)
    dictionary = convert_dictionary_docx_to_csv(source.getvalue()).content
    with DictionaryCSVReader(dictionary) as reader:
        assert reader.headers == DICTIONARY_COLUMNS
        dictionary_rows = [row for _, row in reader]
    validate_dictionary_rows(dictionary_rows)
    assert (
        serialize_csv(
            dictionary_rows,
            columns=DICTIONARY_COLUMNS,
            profile=DictionaryCSVProfile(line_ending="\r\n"),
        )
        == dictionary
    )

    png = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(png, format="PNG")
    uri = build_data_uri(png.getvalue(), "image/png")
    source_row = dict.fromkeys(QAOS_COLUMNS, "")
    source_row.update(
        question_number="1",
        question_text=f'<p>apple café</p><img src="{uri}" data-img-index="0">',
        option_a="fruit",
        answer="A",
        explanation="A fruit at the café.",
        train='["<p>practice</p>"]',
        flip_front='["<p>front</p>"]',
        flip_back='["<p>back</p>"]',
        original_image=serialize_original_images(
            [
                {
                    "column": "question_text",
                    "index": 0,
                    "original_mime": "image/png",
                    "original_data_uri": uri,
                }
            ]
        ),
    )
    payload = serialize_csv([source_row])
    target = io.BytesIO()
    tagging = tag_qaos_csv(dictionary, payload, target)
    tagged = target.getvalue()
    with QAOSCSVReader(tagged) as reader:
        validate_qaos_headers(reader.headers)
        tagged_rows = [row for _, row in reader]
    assert len(tagged_rows) == 1
    row = tagged_rows[0]
    validate_qaos_row(row, row_number=2)
    assert all(row[column] == source_row[column] for column in NON_GENERATION_COLUMNS)
    assert uri in row["question_text"]
    parsed = parse_cell(row["question_text"])
    assert parsed.contains_dictionary_tag and parsed.contains_image
    assert uri.split(",", 1)[1] not in repr(parsed)
    assert protect_segments(row["question_text"]).restore() == row["question_text"]
    second = io.BytesIO()
    assert tag_qaos_csv(dictionary, tagged, second).stats["matched_tags"] == 0
    assert second.getvalue() == tagged
    assert tagging.stats["matched_tags"] > 0
    assert (
        list(csv.DictReader(io.StringIO(serialize_csv(tagged_rows).decode()), delimiter="\t"))
        == tagged_rows
    )

    # Use the real renderer's installed dependencies, isolated from the tagger's
    # generic 'src' package and its process-global csv.field_size_limit changes.
    renderer_code = """
import io, json, sys, zipfile
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from convert_csv_to_docx import convert_csv_to_docx
from convert_csv_to_docx.contracts import ALL_KNOWN_COLUMNS, FLATTENED_CELLS_PER_ROW
from lxml import etree
result = convert_csv_to_docx(sys.stdin.buffer.read())
assert result.output_bytes
with zipfile.ZipFile(io.BytesIO(result.output_bytes)) as package:
    root = etree.fromstring(package.read('word/document.xml'))
    text = ''.join(root.itertext())
    assert 'apple' in text and 'café' in text
    assert any(name.startswith('word/media/') for name in package.namelist())
print(json.dumps({'columns': list(ALL_KNOWN_COLUMNS),
                  'render_slots': FLATTENED_CELLS_PER_ROW, 'docx_bytes': len(result.output_bytes)}))
"""
    completed = subprocess.run(
        [
            str(args.renderer_python),
            "-c",
            renderer_code,
            str(args.projects_root / "csv_to_docx_task" / "src"),
        ],
        input=tagged,
        capture_output=True,
        check=True,
        timeout=60,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    render = json.loads(completed.stdout)
    assert tuple(render["columns"]) == QAOS_COLUMNS
    assert render["render_slots"] == 28
    if args.capture_dir is not None:
        args.capture_dir.mkdir(parents=True, exist_ok=True)
        (args.capture_dir / "dictionary.tsv").write_bytes(dictionary)
        (args.capture_dir / "tagged.tsv").write_bytes(tagged)
    print(
        json.dumps(
            {
                "status": "passed",
                "dictionary_rows": len(dictionary_rows),
                "tagger_idempotent": True,
                "render_slots": render["render_slots"],
                "dictionary_sha256": hashlib.sha256(dictionary).hexdigest(),
                "tagged_sha256": hashlib.sha256(tagged).hexdigest(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
