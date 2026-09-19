# Cross-project contract-test specification

Run these tests in a clean environment using the same pinned `qaos-common` wheel that will ship
with each consumer.

## QAOS pipeline

1. Convert the representative DOCX fixture with `docx_to_csv_task`.
2. Validate headers using strict `qaos/1.0` mode and validate every row.
3. Tag it with `tag_dict_to_qaos_csv`; assert row order/header order, idempotency, and exact
   preservation of unmodified cells and protected data URIs.
4. Enhance it with `multimedia_enhancement_task`; assert existing images are skipped, prompts do
   not contain `base64,`, and original images are appended rather than replaced.
5. Convert with `csv_to_docx_task`; inspect text, nested table/list, style/color, LaTeX, and image
   placement in the final DOCX.

Include UTF-8 and BOM input, LF/CRLF, a quoted multiline cell, two images in one cell, a cell over
10 MiB, legacy `original_image`, and intentional cancellation. Assert no log/error/event includes
the fixture's unique base64 sentinel.

## Dictionary pipeline

1. Convert a dictionary DOCX with `dict_docx_to_csv_task`.
2. Validate strict `dictionary/1.0` headers, non-empty words, unique IDs, and optional image URIs.
3. Tag the QAOS fixture and assert repeated execution is idempotent.

## Platform matrix

The release gate is Python 3.11 on current macOS and Windows. Python 3.12 and 3.13 may be added
without weakening the 3.11 gate.

