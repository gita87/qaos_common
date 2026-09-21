# Local verification: qaos-common 0.2.1

This is a local development build toward production readiness. Scope is qaos_common;
no sibling project was migrated, committed or given a replacement dependency in this update.

## Changes verified

- Upload budgets apply to all CSV source types during reading, including non-seekable
  streams, multibyte text, BOM/newlines and files that grow after opening.
- Parser field limits are restored per operation across nested/concurrent common readers.
- ParsedCell repr exposes metadata only. Row validation checks extra columns, arrays and
  provenance with structured context. Existing dictionary NA and data-dict-id are supported.
- Writer tests cover publication races, no hard-link support, overwrite failure, checkpoints
  and partial stream writes without claiming a change to the existing atomicity contract.

## Evidence

- 108 common tests passed; branch-inclusive coverage 95.30%.
- Ruff passed; strict mypy passed for all 17 package source files.
- The built wheel passed the same 108 tests without source-path injection.
- The live three-project probe passed against the built wheel: two dictionary rows,
  byte-identical dictionary round trip, idempotent tagging, and actual DOCX text/image
  rendering with 26 input columns and 28 render slots.
- Wheel SHA-256: `797c150b8cbb62101dc017cf4727cab58f40117bc9ba0d291483ad4b7b67673f`.
- Dictionary fixture SHA-256:
  `fd36f9bdcca69a96174c81391b9bc280b270f3457f274d495b7dbcfbc060b4d2`.
- Tagged fixture SHA-256:
  `edb6658db427afd1a47e2adfd105ee1c52c9d070f125f99eb01e3110d3915e96`.

Validation used Python 3.11 on macOS. Windows and other supported Python versions were
not run. Portable writer failure tests do not substitute for a Windows run. Full sibling
regression suites were not run because their implementations did not change; only the
documented real data boundaries were exercised. The CSV-to-DOCX project's existing
modified notebook was left untouched.

The current common branch is retained. No merge, Git tag, registry publication or consumer
installation is part of this update. Existing consumer pins to 0.2.0 remain as they were.
See [consumer contracts](consumer-contracts.md) for the explicit future migration gates.
