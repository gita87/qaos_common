# qaos-common

`qaos-common` is the offline, deterministic source of truth for QAOS data contracts. It
provides versioned schemas, bounded streaming CSV I/O, rich-content inspection, safe
`original_image` metadata, and shared operational contracts. It deliberately contains no UI,
server, AI client, prompt, or product-specific conversion workflow.

Requires Python 3.11–3.13.

See the normative [QAOS 1.0 contract](docs/contract-v1.md) and
[consumer contract map](docs/consumer-contracts.md). Version 0.2.2 is the current local
baseline for consumer standardization; see [installation and verification](docs/consumer-readiness.md).
Version 0.2.1 strengthened the shared
reference using actual dictionary, tagging and CSV-to-DOCX boundaries. This is local
development under testing toward production readiness; consumer migrations remain separate.

## Install

```bash
python -m pip install -e .
# Development environment:
python -m pip install -e '.[dev]'
```

## Validate schemas

```python
from qaos_common.schemas import QAOS_COLUMNS, validate_qaos_headers

result = validate_qaos_headers(QAOS_COLUMNS)
assert result.valid

# Compatible mode requires every canonical column in canonical relative order,
# but reports rather than rejects additional columns.
result = validate_qaos_headers((*QAOS_COLUMNS, "consumer_note"), mode="compatible")
assert result.extra == ("consumer_note",)
```

The schema identifiers (`qaos/1.0`, `dictionary/1.0`) are independent of the package version.

## Stream CSV safely

```python
from qaos_common.csvio import QAOSCSVReader, QAOSCSVWriter
from qaos_common.schemas import QAOS_COLUMNS, validate_qaos_headers

with QAOSCSVReader("input.tsv") as reader:
    validate_qaos_headers(reader.headers)
    with QAOSCSVWriter("output.tsv", columns=QAOS_COLUMNS, input_path="input.tsv") as writer:
        for row_number, row in reader:
            writer.write_row(row)
```

Readers accept paths, bytes, and binary/text streams; tolerate UTF-8 BOM and LF/CRLF; and yield
one row at a time. Upload budgets apply during reads for every input type. CSV parser limits
are guarded per operation for nested/concurrent common readers. Writers serialize to a unique
temporary file and atomically publish only on
success. Binary stream destinations stay open; `serialize_csv(rows)` returns identical bytes.
QAOS writers default to QUOTE_ALL and normalize scalar newlines to spaces; arrays are compact
JSON with escaped newlines. Set `QAOSCSVProfile(scalar_newlines="preserve")` for multiline cells.
Existing destinations and the declared input path are protected unless `overwrite=True`.
Use `DictionaryCSVProfile(write_bom=..., line_ending=...)` for dictionary exports.

## Parse and protect rich content

```python
from qaos_common.rich_content import parse_cell, protect_segments

parsed = parse_cell('<p>Area is $x^2$</p><img src="data:image/png;base64,...">')
print(parsed.plain_text)  # safe visible text; no markup or base64
print(parsed.contains_image)  # True

protected = protect_segments(original_cell)
safe_working_text = protected.text
restored = protected.restore()  # byte-for-byte equal to original_cell
```

Protection covers image data URIs, LaTeX, HTML attributes, dictionary spans, and style/script
blocks. Do not send `original`, protected segment values, or raw cells to an agent or logger;
send `plain_text` and boolean/count metadata only. Segment representations redact their values.

## `original_image`

Writers emit a compact JSON array. Readers additionally accept a single JSON object and legacy
Python literal dictionaries/lists through `ast.literal_eval` (never `eval`).

```python
from qaos_common.schemas import append_original_image, parse_original_images

value = append_original_image(
    "",
    {
        "column": "question_text",
        "index": 0,
        "original_mime": "image/png",
        "original_data_uri": png_data_uri,
    },
)
records = parse_original_images(value)
```

The MIME in each record must match both the URI MIME and the decoded signature.

## Limits, progress, and cancellation

```python
from qaos_common import CancellationToken, ProcessingLimits, ProgressEvent

limits = ProcessingLimits(max_cell_bytes=32 * 1024 * 1024)
token = CancellationToken()
token.raise_if_cancelled()
event = ProgressEvent("reading", current=25, total=100, row_number=25)
```

Canonical stages are `validating`, `reading`, `parsing`, `tagging`, `scoring`, `generating`,
`converting_image`, `writing`, `exporting_docx`, and `completed`.

## Stable error codes

All public library errors derive from `QAOSCommonError`. Messages and structured details redact
data URIs, long base64 strings, and byte buffers.

| Code | Meaning |
|---|---|
| `QAOS_SCHEMA_INVALID` | QAOS headers or row violate the contract |
| `DICTIONARY_SCHEMA_INVALID` | Dictionary headers, fields, or ID uniqueness are invalid |
| `CSV_FILE_TOO_LARGE` | Input size or row count exceeds limits |
| `CSV_CELL_TOO_LARGE` | A cell or decoded image exceeds limits |
| `CSV_OUTPUT_TOO_LARGE` | Serialized output exceeds limits |
| `DATA_URI_INVALID` | Data URI syntax, base64, or MIME is unsupported |
| `IMAGE_MIME_MISMATCH` | Declared MIME disagrees with magic bytes |
| `ORIGINAL_IMAGE_INVALID` | `original_image` metadata is invalid |
| `PROTECTED_SEGMENT_INVALID` | A placeholder is missing, repeated, or unknown |
| `PROCESS_CANCELLED` | Cooperative cancellation was requested |

## Migration guide

Migrate one consumer at a time and retain its old import surface as a compatibility shim.

1. **docx_to_csv_task** — depend on `qaos-common`; re-export QAOS schema names from the old schema
   module; adapt its writer; then adopt shared limits, progress, and errors.
2. **csv_to_docx_task** — replace CSV access, data-URI detection, and `original_image` parsing;
   keep DOCX conversion in that project.
3. **dict_docx_to_csv_task** — adopt the dictionary schema/profile and data-URI validator; keep
   Flask/UI and DOCX conversion outside this package.
4. **tag_dict_to_qaos_csv** — protect markup, LaTeX, and data URIs before matching; operate only on
   visible text; skip image/`original_image` columns; preserve unchanged cells exactly.
5. **multimedia_enhancement_task** — give agents only `ParsedCell.plain_text` plus metadata; skip
   cells with `contains_image`; use shared progress/cancellation while retaining image generation
   and conversion in the consumer.

The [consumer contract map](docs/consumer-contracts.md) documents BOM/CRLF and `NA` dictionary
compatibility, `data-dict-id` markup, preservation versus canonical export, and the renderer's
26-column input versus 28 output slots. It includes an optional live probe for all three projects.

For each migration, run the consumer's tests before and after, validate the output headers, and
round-trip an unchanged fixture byte/cell-wise. See [contract tests](docs/contract-tests.md).

## Development

```bash
pytest --cov=qaos_common --cov-report=term-missing
ruff check .
mypy src
python -m build
```

The large-cell test creates data in a temporary directory at runtime; large binary fixtures are
not committed to the repository.
