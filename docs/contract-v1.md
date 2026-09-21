# QAOS interchange contract

Schema ID: `qaos/1.0`. Rich-content ID: `qaos-html/1`. Package release: `0.2.2`.
Schema IDs describe data, not Python package versions. The 26 columns in `QAOS_COLUMNS`
are authoritative, in order. `qaos_schema` in the DOCX engine remains an import shim.

## Array cells and rich content

`flip_front`, `flip_back`, and `train` are compact JSON arrays, serialized with
`ensure_ascii=False`, `allow_nan=False`, and `separators=(",", ":")`. Arrays may contain
nested JSON values; rich strings inside them use `qaos-html/1`. Empty output is `[]`.
The writer accepts lists, tuples, existing JSON arrays, and legacy blank/None cells.
It rejects non-array JSON and non-finite numbers. It never emits Python list syntax.

`validate_qaos_row(row, row_number=..., mode="strict")` checks required/extra columns,
all three arrays, and `original_image`. `mode="compatible"` permits extra columns only;
required columns and valid cells remain mandatory. Native lists/tuples, serialized JSON
arrays, and legacy blank/None array cells are accepted without changing the input row.
Failures use `QAOS_SCHEMA_INVALID`, `stage="validating"`, and include the supplied
`row_number`; cell failures also identify `column`. Question numbering and answer semantics
belong to consumers, so common does not impose numeric IDs or A–I-only answers.

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

Native provenance mappings/lists are accepted as well as serialized representations.
From 0.2.2, QAOSCSVWriter and the default serialize_csv profile also canonicalize
original_image: every accepted input emits compact JSON; empty/None emits []. Invalid
provenance is rejected before its row is written. A generic CSVProfile preserves the
original cell string for consumers that require exact cell-value preservation.
`ParsedCell.__repr__` contains lengths/counts/flags only, never original or plain cell text.
Dictionary spans include the tagger's `data-dict-id` attribute; LaTeX protection includes
matching `\\begin{...}...\\end{...}` environments.

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

Readers enforce upload budgets during reads, for paths, bytes, binary streams and text
streams, including non-seekable streams and files growing after opening. Binary input
counts raw bytes including BOM and CRLF. Text input counts UTF-8 bytes of the supplied
characters; any newline/encoding transformation already performed by the caller cannot
be reconstructed. Limits apply from the supplied stream's current position until EOF.
Validation is streaming: an early-closed reader has not checked unread input. Oversized
input is rejected at the point it is encountered, which may be header acquisition due to
bounded decoder read-ahead. Caller streams remain open on both success and failure.

CSV parser operations share a process-local reentrant lock. Each operation sets and
restores `csv.field_size_limit()` under that lock; no lock is held between yielded rows.
Independent common readers can be nested, closed in any order, or run in separate threads.
Concurrent iteration over the same reader is not supported. Legacy code that independently
mutates the global parser limit must migrate to this reader (or run in a separate process);
the common lock cannot coordinate arbitrary outside mutations.

Dictionary/1.0 is a separate transport profile: existing dictionary exports use UTF-8 BOM,
tab, CRLF, QUOTE_MINIMAL. Select `DictionaryCSVProfile(line_ending="\r\n")` to reproduce it.
The default dictionary profile retains LF for compatibility. Empty/None images and the
exact `NA` sentinel are accepted. IDs such as `'0001` are preserved; adding/removing the
apostrophe and imposing a nonempty definition remain consumer policies.

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

Version 0.2.1 fixes input guards and validates actual row values. Existing invalid array
cells and strict-mode extra columns that passed the old validator now fail. Malformed CSV
and empty/duplicate headers are rejected instead of silently losing or accepting fields.
Cross-project adapters and current migration gaps are documented in
[consumer contracts](consumer-contracts.md). This is a local development build toward
production readiness; a branch, tag, remote or registry is not proof of runtime readiness.
