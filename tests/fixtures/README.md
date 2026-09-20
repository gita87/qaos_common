# Real converter fixture

`converter.tsv` was captured from the unmodified `docx_to_csv_task` engine before this
migration, using Python 3.11 and default ProcessingConfig. `source.xml` is the DOCX body;
the package was constructed with that project's `tests/conftest.py:make_docx` helper.
It contains a Unicode question and answers. The contract test reads these real output
bytes and asserts exact reserialization. Additional synthetic tests cover multiline,
arrays, quoting and limits; consumer integration tests cover images and rich HTML.
