# QAOS interchange contract

Schema ID: `qaos/1.0`. Rich-content ID: `qaos-html/1`. Package release: `0.2.0`.
Schema IDs describe data, not Python package versions. The 26 columns in `QAOS_COLUMNS`
are authoritative, in order. `qaos_schema` in the DOCX engine remains an import shim.

## Array cells and rich content

`flip_front`, `flip_back`, and `train` are compact JSON arrays, serialized with
`ensure_ascii=False`, `allow_nan=False`, and `separators=(",", ":")`. Arrays may contain
nested JSON values; rich strings inside them use `qaos-html/1`. Empty output is `[]`.
The writer accepts lists, tuples, existing JSON arrays, and legacy blank/None cells.
It rejects non-array JSON and non-finite numbers. It never emits Python list syntax.

Rich content is opaque to CSV serialization. HTML, CSS attributes, LaTeX and image data
URIs are retained; there is no Flutter adaptation or HTML sanitization in this package.
`parse_cell` is an inspection boundary, not a renderer or sanitizer. Use its plain text
and flags for downstream inspection. Rendering and wrapper generation stay in the engine.
`ProcessingResult.df_interchange` is the canonical rich boundary; `df_final` and output
bytes may use the consumer's selected rendering profile.

`original_image` writers emit compact JSON arrays of validated records. Required fields:
`column`, nonnegative integer `index`, `original_mime`, `original_data_uri`. Optional
`style` (string) and `value_path` (array of string/integer path components) are preserved.
Readers additionally accept legacy object/Python-literal representations. Image conversion
and DOCX media budgets remain consumer responsibilities.

## CSV transport

QAOS output uses tab delimiters, UTF-8 without BOM, LF record endings, doubled double
quotes and `QUOTE_ALL` by default. `QUOTE_MINIMAL` is supported explicitly.
Scalar CRLF, CR and LF become one space per newline sequence. Array strings are JSON
encoded first, so their embedded newlines survive as escaped `\\n`/`\\r` sequences.
This produces one physical line per record. No stripping of tabs or Unicode occurs.

`QAOSCSVProfile(scalar_newlines="preserve")` is an explicit compatibility mode for lossless
multiline scalar cells. Such cells are quoted and may span physical lines; consumers must
use a CSV reader, not splitlines. Readers also accept BOM and CRLF input.
Dictionary and generic CSV profiles are separate and may choose other transport settings.

`serialize_csv(rows)` returns bytes. `QAOSCSVWriter(path_or_binary_stream)` writes the
same bytes. Binary streams are caller owned, never closed or repositioned. Text streams
are not writer destinations because their encoding/newline translation cannot guarantee
this contract. A failed stream operation may leave prior complete records (or a partial
record on an I/O failure); only path output is atomic. All destinations enforce byte,
cell and row budgets, including the header. Writer objects are single-use.

## Operations

Shared stages are `validating`, `reading`, `parsing`, `tagging`, `scoring`, `generating`,
`converting_image`, `writing`, `exporting_docx`, `completed`. Converter checkpoint names
remain in its compatibility event; `event.to_common()` translates them:

| Converter operation | Shared stage |
| --- | --- |
| extract_ooxml | reading |
| convert_images_to_webp | converting_image |
| rich_cell_contract, interchange_schema, final_schema, validate, validate_rendered_media_budget | validating |
| serialize_output, write_output | writing |
| remaining transform/checkpoint operations | parsing |
| final successful checkpoint notification | completed |

The explicit complete mapping lives in `qaos_docx_engine.control.CONVERTER_PROGRESS_STAGES`.
Current/total count completed checkpoints. No percentage reset occurs between stages.
Cancellation stays cooperative, including the converter's checks around each checkpoint.

Every `QAOSCommonError.to_dict()` returns `{code, message, stage, details}`. `stage` is null
when unknown and may contain the consumer checkpoint for precision. Details and messages
are redacted. Consumer exception classes, RuntimeError inheritance, and existing error
codes remain compatible; common errors retain their stable uppercase codes.

## Migration and release

Migration order: schema → original_image → CSV serialization → limits → cancellation →
progress → errors → rich-content boundary. Compatibility modules adapt existing APIs.
The engine retains OOXML, its 23 checkpoints, Flutter, WebP conversion, ZIP/XML safety,
viewer and webapp. Version 0.2.0 marks the changed writer defaults (quoting, scalar newline
normalization, and array canonicalization). Use explicit preserve mode for prior multiline
behavior. Install the identical vendored wheel in every migrated consumer; record SHA-256.
