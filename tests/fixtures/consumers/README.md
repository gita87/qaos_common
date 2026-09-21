# Actual sibling outputs

Captured with `examples/check_consumer_boundaries.py` from the unmodified sibling
repositories listed in `docs/consumer-contracts.md`. No consumer was migrated to
qaos-common by this capture.

- `dictionary.tsv`: output of `qaos_dictionary.convert_dictionary_docx_to_csv` from
  an in-memory DOCX table (word/definition; apple/fruit; café/coffee house).
  Includes the producer's BOM, CRLF, apostrophe-prefixed IDs and `NA` sentinel.
- `tagged.tsv`: output of `src.tagger.tag_qaos_csv` using that dictionary on a
  common-generated QAOS row with HTML, a valid 2x2 PNG, provenance, and array cells.
  Tagging it twice produced identical bytes and zero new matches the second time.
  The unchanged CSV-to-DOCX consumer rendered these bytes to a DOCX containing
  text and an embedded image, with its own 28-slot layout contract intact.

The capture script records SHA-256 values and supports `--capture-dir`. Normal
unit tests use these small frozen files and need no sibling checkout or renderer.
The optional live probe requires python-docx and Pillow plus the renderer's existing
Python environment. It only writes the requested capture directory, if supplied.
