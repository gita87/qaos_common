# Dependency baseline for consumer standardization

Use **qaos-common 0.2.2** from this repository's `dist/qaos_common-0.2.2-py3-none-any.whl`.
Use the same file and SHA-256 in every consumer; record the hash from
`dist/SHA256SUMS-0.2.2`. Previous wheels remain available for reproducibility, but they are
not the baseline for new migrations. Version 0.2.2 fixes canonical original_image export
for native lists/mappings accepted by the validator. Schema identifiers do not change:
`qaos/1.0`, `dictionary/1.0`, `qaos-html/1`.

## Install into the consumer's own Python environment

From the consumer project, use its supported interpreter (Python 3.11–3.13 declared;
Python 3.11 on macOS verified locally):

```sh
python -m pip install /Users/gitasuputra/Projects/qaos_common/dist/qaos_common-0.2.2-py3-none-any.whl
python -m pip check
python -c "from importlib.metadata import version; import qaos_common; print(version('qaos-common')); print(qaos_common.__file__)"
```

Pin `qaos-common==0.2.2` in the consumer's dependency declaration, and keep the exact wheel
or an explicit local wheel installation step. The package is distributed locally, so a
bare version pin does not provide a downloadable package from an index. Verify the wheel
hash before installing; imports should resolve to that consumer's site-packages instead
of a copied source tree or an unrelated editable installation.

## API boundaries to adopt

- **Schema:** canonical column constants and row/header validators in `qaos_common.schemas`.
  Strict validation requires all canonical columns; compatible mode only permits extras.
  Keep consumer-specific optional-column completion, answer rules and identifier semantics.
- **Provenance:** parse_original_images / serialize_original_images; native, JSON and supported
  legacy records are accepted. QAOSCSVWriter emits a validated compact JSON array and `[]`
  for empty provenance. Invalid provenance aborts path publication.
- **Canonical QAOS export:** QAOSCSVWriter / serialize_csv use tab, UTF-8 without BOM, LF,
  QUOTE_ALL, compact arrays, scalar newline normalization. Path/bytes/binary stream agree.
- **Dictionary export:** DictionaryCSVProfile(line_ending="\r\n") retains the existing
  dictionary producer's BOM/CRLF contract and `NA` marker. ID formatting stays local.
- **Unchanged cell preservation:** generic CSVWriter + CSVProfile(scalar_newlines="preserve")
  leaves pre-serialized cell strings unchanged. Use this for tagger no-change guarantees;
  canonical QAOS export deliberately normalizes structured cells.
- **Operations:** adapt legacy callback/property signatures to shared limits, cancellation,
  ProgressEvent and the `{code,message,stage,details}` error envelope. Preserve old public
  imports and consumer exception behavior through shims.

The [consumer contract map](consumer-contracts.md) gives the detailed adapters for the
three sibling projects. Their internal DOCX/rendering/matching logic stays in those projects.

## What readiness means here

This is a tested local dependency baseline for migration, not a claim that every consumer
has already been migrated or that every platform has been exercised. Before switching a
consumer, run its own regression suite and pin the tested wheel. Do not mix independently
mutating csv.field_size_limit implementations with concurrent common readers: migrate the
CSV boundary or isolate legacy processing in a separate process.

Shared source tests, static checks, wheel/source equivalence, clean wheel installation,
and the real dictionary → tagger → DOCX boundary probe are release checks. Windows and
Python 3.12/3.13 have not been run locally; their coverage must not be inferred from macOS.
The existing portable writer tests cover safe failure when hard links are unsupported.
