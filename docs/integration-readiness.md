# Integration readiness

This document is the handoff for consumers of `qaos-common`. It records the
repository state that was verified locally; it does not claim that a consumer
has already migrated or that an unexecuted platform/CI job passed.

## Baseline and status

| Area | Status | Evidence or boundary |
| --- | --- | --- |
| `qaos/1.0`, `dictionary/1.0`, `qaos-html/1` identifiers | Available | `src/qaos_common/schemas` and [contract-v1](contract-v1.md) |
| Canonical QAOS CSV export | Available | `QAOSCSVWriter` and `serialize_csv` |
| Dictionary transport compatibility | Available | `DictionaryCSVProfile` and `MISSING_DICTIONARY_IMAGE` |
| Bounded streaming I/O and atomic path publication | Available | `tests/test_csvio.py`, `tests/test_reader_boundaries.py`, `tests/test_writer_atomicity.py` |
| Redacted errors, cancellation and progress contracts | Available | `src/qaos_common/errors.py`, `cancellation.py`, `progress.py` |
| Contract fixtures | Available | `tests/fixtures` and synthetic cases in `tests/` |
| Linux CI workflow | Prepared | `.github/workflows/quality.yml`; execution requires the repository CI service |
| Consumer migrations | Not verified here | Consumer repositories are intentionally out of scope |
| Windows and Python 3.12/3.13 execution | Not verified locally | Do not infer these results from macOS Python 3.11 |

## Supported public API

Consumers may import these names from the documented package modules:

```python
from qaos_common import (
    CancellationToken, DEFAULT_LIMITS, PROGRESS_STAGES,
    ProcessingLimits, ProgressEvent, QAOSCommonError,
)
from qaos_common.csvio import (
    CSVProfile, CSVReader, CSVWriter, DictionaryCSVProfile,
    DictionaryCSVReader, DictionaryCSVWriter, QAOSCSVProfile,
    QAOSCSVReader, QAOSCSVWriter, serialize_csv,
)
from qaos_common.schemas import (
    ARRAY_COLUMNS, DICTIONARY_COLUMNS, DICTIONARY_SCHEMA_VERSION,
    QAOS_COLUMNS, QAOS_SCHEMA_VERSION, RICH_CONTENT_FORMAT,
    append_original_image, parse_original_images, serialize_array,
    serialize_original_images, validate_dictionary_headers,
    validate_dictionary_row, validate_dictionary_rows,
    validate_original_image, validate_qaos_headers, validate_qaos_row,
)
from qaos_common.rich_content import (
    build_data_uri, contains_image_data_uri, decode_data_uri,
    find_data_uris, parse_cell, protect_segments, restore_segments,
    validate_image_data_uri,
)
```

`qaos_common.__init__`, `csvio.__init__`, `schemas.__init__`, and
`rich_content.__init__` are the supported import surfaces. Names in private
modules, names beginning with `_`, and implementation details are not public.
The package import is offline and has no server startup, network request,
working-directory change, or file write.

## Stable data contracts

`QAOS_COLUMNS` is the canonical 26-column order:

```text
question_number, question_text, option_a, option_a_image, option_b,
option_b_image, option_c, option_c_image, option_d, option_d_image,
option_e, option_e_image, option_f, option_f_image, option_g,
option_g_image, option_h, option_h_image, option_i, option_i_image,
answer, explanation, flip_front, flip_back, train, original_image
```

All CSV cells are transported as strings. QAOS requires every canonical column;
strict mode rejects extra columns, while compatible mode reports and permits
extras. Dictionary/1.0 has the ordered columns `unique_id`, `word`,
`definition`, `image`; `unique_id` and `word` are required and IDs must be
unique when validating a collection. Dictionary image may be empty or the
literal `NA`, otherwise it must be a valid image data URI.

QAOS `flip_front`, `flip_back`, and `train` are compact JSON arrays using
UTF-8, `ensure_ascii=False`, `allow_nan=False`, and no optional whitespace.
Blank legacy array cells become `[]`. `original_image` is a compact JSON array
on canonical export; readers also accept a single object and safe legacy
Python-literal values. Each record requires `column`, nonnegative integer
`index`, `original_mime`, and `original_data_uri`; optional `style` and
`value_path` are preserved. The URI MIME, decoded signature, and declared MIME
must agree.

Canonical QAOS export uses tab, UTF-8 without BOM, LF, and `QUOTE_ALL` by
default. Scalar CRLF/CR/LF becomes one space; array newlines are JSON-escaped.
`QAOSCSVProfile(scalar_newlines="preserve")` is the explicit multiline mode.
Readers accept UTF-8 BOM and LF/CRLF. Dictionary compatibility exports use
UTF-8 BOM, tab, CRLF, and minimal quoting when
`DictionaryCSVProfile(line_ending="\r\n")` is selected. A generic
`CSVProfile` preserves pre-serialized cell strings and is the correct boundary
for no-change/preservation workflows; it is not canonical QAOS export.

The `qaos-html/1` rich-content value is opaque to CSV I/O. HTML, LaTeX, CSS
attributes, and image data URIs are preserved. `parse_cell` exposes safe plain
text and metadata for inspection; it is not a sanitizer or renderer. An image
URI is a `data:<mime>;base64,...` value validated against supported magic bytes.

## Operational boundaries

All public library errors derive from `QAOSCommonError` and serialize as
`{code, message, stage, details}`. Messages and details redact data URIs,
long base64 values, byte buffers, and protected content. Cancellation is
cooperative through `CancellationToken`; progress uses the stages in
`PROGRESS_STAGES`. Limits cover input bytes, rows, cells, decoded images, and
output bytes.

Path writers publish through a temporary file and atomic operation. Binary
streams belong to the caller and remain open; they may contain complete or
partial output if a write fails. Readers likewise leave caller streams open.
Reader operations restore the shared CSV parser limit after success and error;
concurrent iteration over one reader is not supported.

## Contract fixtures and verification

Fixtures are small and deterministic. `tests/fixtures/consumers` contains
dictionary and tagged outputs with BOM/CRLF, `NA`, rich HTML/LaTeX, arrays,
image data URI, and `original_image`. `tests/fixtures/converter.tsv` covers a
representative QAOS export. Synthetic tests cover valid/invalid data URIs,
multiline and Unicode cells, duplicate/missing headers, malformed rows, large
cells, cancellation, redaction, stream ownership, atomic failure, and parser
state restoration. No client document data is used.

## Clean install and artifact verification

The current consumer baseline remains **0.2.2**. Existing artifacts are kept;
they are not overwritten by this readiness work.

```sh
python -m pip install --force-reinstall \
  /Users/gitasuputra/Projects/qaos_common/dist/qaos_common-0.2.2-py3-none-any.whl
python -m pip check
python -c 'from importlib.metadata import version; import qaos_common; print(version("qaos-common")); print(qaos_common.__file__)'
shasum -a 256 dist/qaos_common-0.2.2-py3-none-any.whl dist/qaos_common-0.2.2.tar.gz
```

Recorded SHA-256 values:

```text
f0218d9a9e670fdf997dd69c16c8eccb8bc55414a196c449f64c35d3959a0588  qaos_common-0.2.2-py3-none-any.whl
31368af06d86c7b6d0385ea81d7f16fdf610d92c8eba25d74700caa9e748eb5c  qaos_common-0.2.2.tar.gz
```

For a clean wheel smoke test, install the wheel into a fresh environment in a
directory outside this checkout, run `pip check`, assert that
`qaos_common.__file__` is in that environment's site-packages, and execute the
minimal imports above. Build and test commands are defined in the CI workflow.

## Compatibility and remaining blockers

No schema identifier or output contract changed in this handoff. Consumers
must retain compatibility shims for their old imports, choose canonical QAOS
versus generic preservation deliberately, and keep DOCX/rendering/matching
logic in their own repositories. Before migration, each consumer must run its
own regression suite against the exact wheel and checksum. CI execution,
Windows, Python 3.12/3.13, and all four consumer migrations remain unverified.
