# Shared reference for the QAOS projects

Scope: improve and test **qaos_common**. The three sibling projects are read-only
references in this change; no dependency, wheel, code or Git state was changed there.
This is pioneering local development under active testing toward production readiness.
The common package is the reference for shared data, not for every consumer's internal
model or rendering rules. `qaos/1.0`, `dictionary/1.0` and `qaos-html/1` remain distinct.

## Contract map

| Project | Shared reference | Consumer-owned behavior |
| --- | --- | --- |
| csv_to_docx_task | QAOS_COLUMNS, CSVReader, validate_qaos_row, original-image/data-URI parsing, shared limits/cancellation/progress/error shape | 28 render slots per question, DOCX layout, image placement, diagnostics, optional-column completion, renderer safety budgets |
| dict_docx_to_csv_task | DICTIONARY_COLUMNS and dictionary/1.0, dictionary profile, validation, shared operations | DOCX table extraction, whitespace normalization, ID generation and apostrophe export prefix, WebP conversion, ZIP/XML safeguards |
| tag_dict_to_qaos_csv | Both schemas, bounded CSV, protected segments, rich-content flags, shared operations | Term matching, longest-match precedence, dictionary-ID normalization, checkpoint/resume, selecting/skipping cells and idempotence |

The 28 renderer slots include separators; they are not 28 QAOS columns. Canonical QAOS
has 26 columns. The CSV-to-DOCX consumer additionally accepts missing option columns and
unknown columns under its own policy. Its compatibility adapter must fill/reorder optional
columns before canonical validation. Common `compatible` mode allows extra columns but
does not relax missing canonical columns or ordering.

## Actual differences that adapters must preserve

### csv_to_docx_task

Reference modules: `src/convert_csv_to_docx/contracts.py`, `csv_reader.py`, `normalizer.py`,
`runtime.py`, `api.py`.

- Preserve `ALL_KNOWN_COLUMNS` as a shim for `QAOS_COLUMNS`. Retain `CONTENT_COLUMNS`,
  `FLATTENED_CONTENT_ORDER` and `FLATTENED_CELLS_PER_ROW=28` locally.
- CSVReader exposes physical line numbers; the existing reader reports logical row numbers
  and input hashes/preflight statistics. Preserve these through an adapter rather than
  silently changing diagnostics or losing hashing/accounting.
- Shared provenance parsing accepts legacy input. The renderer's strict/lenient diagnostics,
  unique `(column,index)` requirements, item-count budget and mapping to rendered cells
  remain additional local checks. Its treatment of optional `value_path` is a separate
  rendering concern; the common package preserves that information.
- Existing cancellation exposes an `is_cancelled` property, whereas common exposes a
  method. Retain an adapter and the existing exception class/code.
- Rendering must keep its own image-decoding, XML/ZIP, output and image-placement checks.

### dict_docx_to_csv_task

Reference modules: `qaos_dictionary/core.py`; `tests/test_output_contract.py`.

- Use `DictionaryCSVProfile(line_ending="\r\n")`: tab, UTF-8 BOM, CRLF, QUOTE_MINIMAL.
  Do not substitute QAOSCSVProfile, which targets a different data format.
- `NA` is the current missing-image marker. Common now validates it alongside empty/None.
  A populated image is a raw image data URI; conversion to WebP remains in the dictionary
  producer. Dictionary row validation reports row/column context for invalid image data.
- Preserve apostrophe-prefixed exported IDs (`'0001`) exactly. Adding that prefix is an
  exporter decision; stripping it before matching is a tagger decision.
- Keep the producer's nonempty-definition rule. The shared minimum requires an ID and
  word, and permits an empty definition for other dictionary consumers.
- Suggested progress adapter: read→reading, validate→validating, extract→parsing,
  serialize→writing, complete→completed. Preserve the existing checkpoint callback.

### tag_dict_to_qaos_csv

Reference modules: `src/tagger.py`, `reader.py`, `writer.py`, `config.py`;
`tests/test_tagger.py`.

- The existing `data-dict-id` markup is now recognized by common. Already-tagged spans,
  LaTeX environments, attributes and image data URIs survive protect/restore exactly.
- For transformations that promise unchanged cell values, use generic `CSVWriter` with
  `CSVProfile(quoting=csv.QUOTE_MINIMAL, scalar_newlines="preserve")` and the input headers.
  QAOSCSVWriter is the canonical export boundary: it normalizes arrays/newlines. It is
  inappropriate when an unchanged serialized array or scalar must be retained literally.
  CSV quoting may differ while cells remain equal; identical whole-file bytes require a
  separate no-op/passthrough policy in the consumer.
- Retain `NON_GENERATION_COLUMNS | set(OPTION_IMAGE_MAP.values())` as skipped columns
  through an adapter. Match only eligible text, then restore protected segments.
- The tagger supports arbitrary tables and a two-column tag/value export as well as full
  QAOS. Use generic CSV facilities for those modes; do not force 26-column validation.
- Common accepts BOM-prefixed dictionaries. The old standalone `read_dict_csv` uses plain
  UTF-8, so its BOM behavior needs explicit migration coverage even though the streaming
  tagger path handles the producer fixture successfully.
- The legacy tagger changes csv.field_size_limit globally. Migrate those parser calls to
  the common reader before claiming safe concurrent common/tagger reads in one process.
- Preserve the old `cancelled` property, `raise_if_cancelled(row)` and error codes via a
  shim. Adapt processed_rows/total_rows to current/total with stage `tagging` and emit
  `completed` only after successful publication.

## Evidence and migration gate

`examples/check_consumer_boundaries.py` exercises the actual existing APIs:

1. Build a two-row dictionary DOCX in memory, convert it with the dictionary project,
   read/validate it with common, then reproduce identical BOM/CRLF bytes.
2. Generate a canonical QAOS row containing Unicode, an image and provenance, and arrays.
   Tag it using the real tagger and dictionary output. Assert skipped fields and image
   data survive, and a second tagging pass makes zero changes.
3. Validate/read/serialize the tagged row through common, then pass the tagged bytes to
   the actual CSV-to-DOCX API. Assert its output contains the text and embedded image,
   and retains the 26-column input / 28-slot rendering distinction.

Run from qaos_common with its dependencies plus python-docx and Pillow available:

```sh
python examples/check_consumer_boundaries.py \
  --projects-root /path/to/Projects \
  --renderer-python /path/to/Projects/csv_to_docx_task/.venv/bin/python
```

The renderer runs in its existing environment in a subprocess. The probe only reads
consumer code; `--capture-dir` optionally saves fixtures under a selected directory.
The small captured dictionary/tagger outputs are kept in `tests/fixtures/consumers` for
normal offline contract tests. This proves the tested data boundaries, not a completed
consumer migration or full regressions of all three projects.

When migration is authorized, pin every migrated consumer to the **same wheel and hash**.
Keep old import/API shims. Adopt schema → original_image → CSV → limits → cancellation →
progress → errors → rich-content boundaries, running each consumer's full regressions.
Do not install a replacement wheel into other projects as part of a common-only update.

## Local release and platform limits

Package 0.2.1 is a local tested build. Work stays on the existing common branch; neither
merging to main nor publishing a tag/registry is required for these contract repairs.
`tests/test_writer_atomicity.py` covers overwrite, a competing publisher, unsupported
hard links, locked-destination failures, checkpoint cleanup and stream ownership. These
tests are portable, but their execution on macOS does not constitute Windows verification.
Run the suite on Windows before claiming that platform has been verified. Filesystems
without hard-link support fail safely in no-overwrite mode; there is no weaker fallback.
