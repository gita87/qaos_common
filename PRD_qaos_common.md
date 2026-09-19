# Product Requirements Document — `qaos_common`

## 1. Document information

| Attribute | Value |
|---|---|
| Product | `qaos_common` |
| Product type | Standalone, reusable Python library |
| Status | Implementation draft |
| Target Python | `>=3.11,<3.14` |
| Distribution name | `qaos-common` |
| Import name | `qaos_common` |
| Initial package version | `0.1.0` |
| Initial QAOS contract version | `qaos/1.0` |
| Initial dictionary contract version | `dictionary/1.0` |
| Platforms | macOS and Windows |

## 2. Product decision summary

`qaos_common` is a standalone library and the shared source of truth for data contracts, CSV
reading and writing, rich-content parsing, capacity limits, progress, cancellation, and errors
across QAOS applications.

It will be used by `docx_to_csv_task`, `csv_to_docx_task`, `dict_docx_to_csv_task`,
`tag_dict_to_qaos_csv`, `multimedia_enhancement_task`, and future QAOS projects.

It has no browser UI, launcher, server, agent, prompt, or OpenAI integration. All behavior must be
deterministic and usable without an internet connection.

## 3. Problem background

Existing QAOS projects perform different functions but share data concepts. Important rules risk
being redefined in each project, including:

- names and order of the 26 QAOS columns;
- the dictionary schema and `original_image` format;
- CSV encoding, delimiter, and maximum size;
- HTML, LaTeX, data URI, and base64 detection;
- progress, cancellation, and error formats;
- columns that may or may not be processed.

Duplication can make projects incompatible. Image data URIs can also make QAOS files too large for
ordinary CSV reading or whole-file in-memory processing.

## 4. Goals

### 4.1 Primary goals

1. Provide one source of truth for QAOS and dictionary schemas.
2. Provide CSV readers and writers that safely handle large base64 cells.
3. Separate visible text from HTML, LaTeX, and data URIs.
4. Prevent base64 from entering agents, prompts, logs, and error messages.
5. Standardize limits, progress, cancellation, and structured errors.
6. Let all five projects share contracts without copying implementations.
7. Preserve compatibility with legacy files and APIs during migration.

### 4.2 Success indicators

- Every project imports schemas from `qaos_common`.
- Files with cells up to configured limits can be streamed.
- Column names and order survive transformation-free CSV round trips.
- HTML, nested tables/lists, colors, styles, and LaTeX survive protection and restoration.
- Protected data URIs are restored byte-for-byte.
- No base64 appears in logs, progress events, or error details.
- Cross-project contract tests pass on Python 3.11 on macOS and Windows.

## 5. Out of scope

The library must not implement web/desktop UI, launchers, a local server, API-key storage, AI
clients, scoring or image-generation prompts, image-suitability decisions, product PNG-to-WebP
workflows, complete DOCX/CSV conversion, application job queues, or project-specific business
rules.

## 6. Consumers

Direct consumers are developers and feature modules, not end users.

| Consumer | Primary use |
|---|---|
| `docx_to_csv_task` | QAOS schema, writer, rich-content utilities, progress, errors |
| `csv_to_docx_task` | QAOS schema, reader, parser, `original_image`, limits |
| `dict_docx_to_csv_task` | Dictionary schema, writer, data URIs, progress |
| `tag_dict_to_qaos_csv` | QAOS I/O, dictionary schema, parser, protected segments |
| `multimedia_enhancement_task` | I/O, target rules, image detection, limits, progress, cancellation |

## 7. Project structure

```text
qaos_common/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
├── src/qaos_common/
│   ├── __init__.py
│   ├── schemas/{__init__.py,qaos.py,dictionary.py,original_image.py}
│   ├── csvio/{__init__.py,reader.py,writer.py}
│   ├── rich_content/{__init__.py,parser.py,data_uri.py,protected_segments.py}
│   ├── limits.py
│   ├── progress.py
│   ├── cancellation.py
│   └── errors.py
└── tests/
```

## 8. Schema contracts

### 8.1 Package and schema versions

Package and schema versions are independent. `qaos-common 1.2.0` is a software version;
`qaos/1.0` and `dictionary/1.0` are data-format versions. A bug fix does not change a schema
version. Changing a column's name, meaning, type, or order requires a schema-version change.

### 8.2 QAOS schema `qaos/1.0`

Canonical column order:

```text
question_number
question_text
option_a
option_a_image
option_b
option_b_image
option_c
option_c_image
option_d
option_d_image
option_e
option_e_image
option_f
option_f_image
option_g
option_g_image
option_h
option_h_image
option_i
option_i_image
answer
explanation
flip_front
flip_back
train
original_image
```

Minimum API:

```python
from qaos_common.schemas.qaos import (
    QAOS_SCHEMA_VERSION,
    QAOS_COLUMNS,
    NON_GENERATION_COLUMNS,
    OPTION_IMAGE_MAP,
    validate_qaos_headers,
    validate_qaos_row,
)
```

`QAOS_SCHEMA_VERSION` is `"qaos/1.0"`. These columns must not be image-generation targets:
`question_number`, `answer`, `flip_front`, `flip_back`, `train`, and `original_image`.

`question_text` and `explanation` may conceptually be targets but have no paired image column.
Calling applications handle in-cell placement; this library only detects existing images and
provides rich-content utilities.

### 8.3 Dictionary schema `dictionary/1.0`

Canonical order is `unique_id`, `word`, `definition`, `image`.

- `unique_id` is required and unique within one file.
- `word` must not be empty.
- `definition` may contain plain text or rich content.
- `image` may be empty or contain a valid image data URI.

### 8.4 `original_image` contract

Canonical output is a valid JSON array:

```json
[
  {
    "column": "question_text",
    "index": 0,
    "original_mime": "image/png",
    "original_data_uri": "data:image/png;base64,..."
  }
]
```

Readers accept a canonical JSON array, a single JSON object, or legacy Python dictionary/list
literals with single quotes through a safe parser—never `eval()`. Writers emit canonical JSON
only and must preserve existing records when appending.

```python
parse_original_images(value)
serialize_original_images(records)
append_original_image(value, record)
validate_original_image(record)
```

## 9. Functional requirements

### FR-001 — Schema validation

Validate names, order, missing columns, and extra columns. In `strict` mode, names and order must
match exactly. In `compatible` mode, all required columns must exist and extra columns are
reported rather than immediately rejected.

### FR-002 — Streaming CSV reader

The reader must accept paths, binary/text streams, or bytes; accept UTF-8 and UTF-8 BOM; support
tab-delimited files; explicitly configure `csv.field_size_limit()`; yield one row at a time;
never materialize the whole file; report row and column context in errors; and preserve cells.

### FR-003 — Safe CSV writer

The writer must preserve schema order, stream rows, support UTF-8 and configurable BOM/line
endings, write through a temporary file, reject input overwrite by default, publish only after
success, and delete or checkpoint temporary output after failure.

### FR-004 — CSV profiles

- `QAOSCSVProfile`: tab delimiter, UTF-8, LF, canonical QAOS quoting.
- `DictionaryCSVProfile`: tab delimiter, configurable UTF-8 BOM and line ending.

Readers tolerate BOM and CRLF/LF. Writers are deterministic for their selected profile.

### FR-005 — Rich-content parsing

Recognize visible text, HTML tags/attributes/entities, inline styles/colors, nested tables and
lists, inline/block LaTeX, image data URIs, dictionary tags, and content unsafe to modify.

```python
ParsedCell(
    original=...,
    plain_text=...,
    contains_html=True,
    contains_latex=True,
    contains_image=True,
    image_count=1,
    protected_segments=...,
)
```

`plain_text` must contain no HTML tags, CSS, base64 payloads, or data URIs.

### FR-006 — Data URI detection

Detect data URIs immediately after HTML tags, in the middle of rich text, with PNG/JPEG/GIF/WebP
content, valid whitespace, or very long payloads. Detection must not decode payloads implicitly.

```python
contains_image_data_uri(value)
find_data_uris(value)
validate_image_data_uri(value)
decode_data_uri(value, limits=limits)
build_data_uri(data, mime_type)
```

### FR-007 — Protected segments

Replace sensitive/raw content with collision-free placeholders and restore it identically.
Protectable content includes data URI/base64, LaTeX, HTML attributes, dictionary spans,
style/script blocks, and application-registered segments. Restoration is byte-for-byte. Missing,
repeated, or unknown placeholders raise structured errors. Payloads never appear in default
representations or logs.

### FR-008 — Processing limits

```python
ProcessingLimits(
    max_upload_bytes=256 * 1024 * 1024,
    max_cell_bytes=64 * 1024 * 1024,
    max_output_bytes=512 * 1024 * 1024,
    max_image_bytes=20 * 1024 * 1024,
    max_rows=100_000,
    max_images_per_row=10,
)
```

Applications may override every value. Negative or unreasonable configurations are rejected.

### FR-009 — Progress

```python
ProgressEvent(
    stage="reading",
    current=25,
    total=100,
    message="Reading row 25",
    row_number=25,
)
```

Canonical stages are `validating`, `reading`, `parsing`, `tagging`, `scoring`, `generating`,
`converting_image`, `writing`, `exporting_docx`, and `completed`. The library defines the contract;
applications decide when and how to display events.

### FR-010 — Cancellation

Provide `token.is_cancelled()`, `token.raise_if_cancelled()`, and `token.cancel()`. Consumer loops
check periodically. Cancellation is distinct from quota exhaustion, invalid credentials, and
provider errors.

### FR-011 — Structured errors

Every public error derives from `QAOSCommonError` and carries a stable code, a user-safe message,
structured details, and optional exception chaining. Required codes:

```text
QAOS_SCHEMA_INVALID
DICTIONARY_SCHEMA_INVALID
CSV_FILE_TOO_LARGE
CSV_CELL_TOO_LARGE
CSV_OUTPUT_TOO_LARGE
DATA_URI_INVALID
IMAGE_MIME_MISMATCH
ORIGINAL_IMAGE_INVALID
PROTECTED_SEGMENT_INVALID
PROCESS_CANCELLED
```

Errors and details must never contain complete base64 payloads.

## 10. Non-functional requirements

### NFR-001 — Compatibility

Support Python `>=3.11,<3.14`, macOS, and Windows without shell-specific dependencies. Use
`pathlib.Path` for paths.

### NFR-002 — Performance and memory

Process CSV row-by-row; never decode data URIs without an explicit request; handle a QAOS fixture
of at least 100 MiB within benchmark limits; and avoid unnecessary base64 copies. Peak streaming
memory should not exceed the largest cell plus documented parser overhead. Unchanged files must
not require whole-file memory.

### NFR-003 — Security

Never use `eval()`. HTML/XML parsers must not retrieve external resources. The library performs no
network access. Base64 and API keys never enter logs. Error previews are truncated and sanitized.
Temporary files use unique names and OS-appropriate permissions.

### NFR-004 — API stability

Export public APIs explicitly through `__all__`. Breaking changes follow SemVer. Experimental
functions stay outside the stable API. Announce deprecations at least one minor release before
removal, except for security fixes.

### NFR-005 — Documentation

The README covers installation, schema validation, streaming I/O, rich-content parsing, protected
segments, `original_image`, error codes, and migration guidance.

## 11. Dependencies

```toml
requires-python = ">=3.11,<3.14"
dependencies = [
    "beautifulsoup4>=4.12,<5",
    "defusedxml>=0.7,<1",
    "lxml>=5,<7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8,<9",
    "pytest-cov>=5,<8",
    "ruff>=0.9",
    "mypy>=1.14,<2",
]
```

`Pillow>=12.3,<13` may be a dependency or optional `images` dependency when image decoding or
magic-byte validation needs it. `python-docx`, pandas, FastAPI, Flask, OpenAI SDK, and web-server
dependencies remain outside this library.

## 12. Initial public API

```python
from qaos_common.csvio import QAOSCSVReader, QAOSCSVWriter
from qaos_common.limits import ProcessingLimits
from qaos_common.rich_content import parse_cell
from qaos_common.schemas.qaos import QAOS_COLUMNS, validate_qaos_headers

limits = ProcessingLimits(max_cell_bytes=64 * 1024 * 1024)

with QAOSCSVReader("input.csv", limits=limits) as reader:
    validate_qaos_headers(reader.headers)
    with QAOSCSVWriter("output.csv", columns=QAOS_COLUMNS) as writer:
        for row_number, row in reader:
            parsed = parse_cell(row["question_text"])
            writer.write_row(row)
```

The public API stays small and stable; internal helpers are not automatically public.

## 13. Multimedia-agent integration

The library does not run agents. It prepares safe data:

```text
CSV cell → parse rich content → detect images → protect base64/markup/LaTeX
         → produce plain text and metadata → application decides whether to call an agent
```

If `question_text` or `explanation` contains an image data URI, `contains_image` is `True`, and
the consumer applies its skip rule. Base64 never enters prompts. Agents receive only plain text,
topic metadata, and indicators such as `contains_existing_image`.

## 14. Legacy-project integration strategy

Migrate one project at a time. Do not import the package before it is installed; retain legacy
helpers temporarily through compatibility shims; and run contract tests before and after.

### 14.1 `docx_to_csv_task`

Add the dependency, re-export the shared schema from the legacy module, adapt the shared writer,
adopt progress/limits/errors, and preserve legacy imports during transition.

### 14.2 `csv_to_docx_task`

Adopt the QAOS reader, limits, `original_image` parser, and rich-content/data-URI detection. Align
the cell limit but retain DOCX conversion in this project.

### 14.3 `dict_docx_to_csv_task`

Add `pyproject.toml` when needed; adopt the dictionary schema, writer profile, and data-URI
validator; separate UI from conversion; and align Python/Pillow versions.

### 14.4 `tag_dict_to_qaos_csv`

Replace raw-cell regex processing with rich-content parsing. Protect base64, LaTeX, tags, and
attributes; tag visible nodes only; use streaming I/O and shared limits; remain idempotent; skip
image and `original_image` columns; and preserve unchanged content.

### 14.5 `multimedia_enhancement_task`

Use shared CSV access, `contains_image`, protected segments, progress, and cancellation. Keep
PNG/WebP conversion, `original_image` workflows, and output creation in the automation project.

## 15. Testing

Unit tests cover all 26 columns; strict/compatible validation; dictionary uniqueness; UTF-8/BOM;
LF/CRLF; cells beyond Python's default limit; HTML styles/colors; nested tables/lists;
inline/block LaTeX; data URIs after `<br/>`; multiple URIs; invalid base64; MIME mismatch;
byte-exact restoration; safe legacy metadata; cancellation; and base64 redaction.

Cross-project QAOS flow:

```text
QAOS DOCX → docx_to_csv_task → qaos_common validation → tag_dict_to_qaos_csv
          → multimedia_enhancement_task → csv_to_docx_task → DOCX
```

Dictionary flow:

```text
Dictionary DOCX → dict_docx_to_csv_task → qaos_common validation → tag_dict_to_qaos_csv
```

Minimum CI: Python 3.11 on macOS and Windows. Additional versions may be added below 3.14.

## 16. Version `0.1.0` acceptance criteria

1. Editable and local-wheel installation work.
2. Imports work on Python 3.11 on macOS and Windows.
3. QAOS and dictionary schemas are public.
4. The reader streams cells larger than 10 MiB without `list(reader)`.
5. The writer does not overwrite input by default.
6. The parser detects representative HTML, LaTeX, and images.
7. Data URIs never appear in `plain_text`.
8. Protection/restoration is identical.
9. Legacy `original_image` is rewritten as canonical JSON.
10. Limits, progress, cancellation, and errors are public.
11. Base64 never appears in fixture logs/errors.
12. Critical-code coverage is at least 90%.
13. Migration guidance is available.

## 17. Development phases

1. **Foundation:** package, schemas, metadata model, limits, errors, schema tests.
2. **CSV I/O:** streaming reader, atomic writer, profiles, enforcement, large fixture.
3. **Rich content:** data URIs, protected segments, parser, security/round-trip tests.
4. **Operations:** progress, cancellation, API documentation, wheel build.
5. **Migration:** migrate the five consumers in the order listed in Section 2.

The tagger still needs a rich-content-aware refactor after adopting the library.

## 18. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Schema changes break legacy projects | High | Versioned schemas, shims, contract tests |
| Base64 consumes excessive memory | High | Streaming, lazy decode, limits, no unnecessary copies |
| HTML changes during round trips | High | Protection, complex fixtures, byte-level tests |
| Legacy metadata is inconsistent | Medium | Safe backward-compatible parser, canonical writer |
| Projects depend on an unstable version | Medium | `0.x`, phased migration, compatible pinning |
| Library accumulates business logic | High | Enforce non-goals and module boundaries |
| Dependency conflicts | Medium | Minimal dependencies and consistent ranges |

## 19. Final decisions

1. `qaos_common` is standalone and has only one shared implementation.
2. Projects import shared contracts after installation.
3. `qaos/1.0` is a schema version, not an import name.
4. Distribution/import names are `qaos-common`/`qaos_common`.
5. Writers emit valid JSON; readers safely accept legacy formats.
6. Base64 is neither sent to agents nor logged.
7. Agents and automation workflows remain outside this package.
8. Legacy projects migrate incrementally through shims.

## 20. Deliverables

- source package and `pyproject.toml`;
- documented public API;
- unit tests and rich-content fixtures;
- large CSV fixture;
- wheel and source distribution;
- changelog;
- migration guide;
- contract-test specification;
- `multimedia_enhancement_task` integration example.
