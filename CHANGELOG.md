# 0.2.2

- Align QAOS CSV provenance serialization with row validation: native mappings/lists,
  legacy values and JSON input emit a validated compact JSON array; blank values emit [].
- Reject invalid provenance before writing its row, with writing-stage and row/column
  context. Generic CSVProfile remains available for exact cell-value preservation.
- Add path/stream/bytes regression tests for every supported provenance representation.

# 0.2.1

- Enforce upload budgets while reading binary/text streams, including non-seekable
  inputs and files that grow after opening; preserve caller stream ownership.
- Isolate CSV parser limits per parsing operation for nested/concurrent readers;
  restore the global setting on success and failure. Reject malformed CSV headers.
- Remove all cell text from ParsedCell repr; protect data-dict-id spans and LaTeX
  environments emitted/handled by the dictionary tagger.
- Validate QAOS extra columns, array contents and image provenance with row context.
  Compatible mode permits extra columns, not invalid values. Retain legacy blank cells.
- Accept the existing dictionary/1.0 NA image sentinel; preserve native image metadata.
- Add real dictionary/tagger fixtures, an opt-in live consumer probe, and portable
  atomic-writer failure tests. Consumer implementations remain independent.

# 0.2.0

- Finalize qaos/1.0 and qaos-html/1 contracts and compact array cells.
- Add binary streams and bytes serialization, explicit newline profiles and atomic cleanup.
- Standardize structured errors with optional stage. Preserve image provenance extensions.
- Add real converter output contract tests and migration documentation.
- Breaking defaults: QAOS uses QUOTE_ALL, scalar newline-to-space, and blank arrays become [].

# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [0.1.0] - 2026-09-20

### Added

- Versioned QAOS and dictionary schemas.
- Streaming, size-limited CSV reader and atomic writer.
- Rich-content, data-URI, and protected-segment utilities.
- Canonical and legacy-safe `original_image` handling.
- Shared limits, progress, cancellation, and structured errors.
