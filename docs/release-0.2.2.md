# Local release verification: 0.2.2

Version 0.2.2 is the local dependency baseline for consumer standardization.
No package registry publication is required for this distribution workflow.
See [consumer readiness](consumer-readiness.md) for installation and migration boundaries.

## Correction

The QAOS writer now exports `original_image` as a validated compact JSON array,
including native lists/mappings already accepted by the row validator. Empty provenance
becomes `[]`; invalid provenance produces a structured writing-stage error before path
publication. Generic CSV profiles continue preserving pre-serialized strings.
Schema identifiers remain `qaos/1.0`, `dictionary/1.0` and `qaos-html/1`.

## Verified on macOS, Python 3.11

- Source suite: 126 tests passed; branch-aware coverage 95.34%.
- Ruff and mypy passed; Git whitespace check passed.
- Fresh virtual environment installed the wheel with dev/images extras and python-docx.
- All 126 tests passed against the installed wheel without a source-path override.
- Distribution metadata and imported package both report 0.2.2; import resolves to the
  fresh environment's site-packages. `pip check` reports no broken requirements.
- All 17 Python source files and `py.typed` match the wheel byte for byte.
- Real sibling-project boundary probe passed: two dictionary rows, idempotent tagging,
  and 28 rendering slots. Consumer source and environments were not modified.

Wheel: `dist/qaos_common-0.2.2-py3-none-any.whl`

SHA-256: `f0218d9a9e670fdf997dd69c16c8eccb8bc55414a196c449f64c35d3959a0588`

Checksums for the wheel and source archive are in `dist/SHA256SUMS-0.2.2`.
Previous release artifacts remain unchanged. Windows and Python 3.12/3.13 were not
executed locally. Each consumer still needs its own regression tests during migration;
the boundary probe does not certify a completed migration.
