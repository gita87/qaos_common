# Local release verification: qaos-common 0.2.0

- Schema: qaos/1.0; rich content: qaos-html/1.
- Wheel: qaos_common-0.2.0-py3-none-any.whl.
- SHA-256: 4e8e718eba648b1b558d4faf7b965d73e862fa15d1e883bccf3f7ba8c54eb72b.
- qaos_common: 42 tests passed, 92.68% branch-inclusive coverage; ruff and mypy pass.
- docx_to_csv_task: all 250 tests passed (249 in the full sandbox run; localhost webapp
  test passed separately with socket permission). One upstream ziamath deprecation warning.
- Installed wheel, rather than editable common source, used for final testing.
- Same wheel/hash installed in qaos_common/.venv and docx_to_csv_task/.venv311.
- Consumer pip check passes. Its previous Python 3.9 environment was retained.
- Consumer mypy reports 23 errors; before migration it reported 25 in the same 9 files.
  These existing pandas typing findings are outside the contract migration.
- Sibling repository dependency/import search found no other current qaos-common consumers.
  Their full migrations are not claimed. Use the same wheel when migrating them.
- Wheel and source archive were built locally; no package registry publication or git tag
  was performed. Windows verification was not run.

The normative contract is contract-v1.md. The converter has MIGRATION-common.md,
requirements-common.txt with an artifact hash, and vendor/SHA256SUMS.
