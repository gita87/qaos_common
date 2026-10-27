# qaos-common 0.2.3 candidate

- Updated optional `images` extra to `Pillow>=13,<14`.
- No shared schemas or serialization behavior changed.
- Wheel SHA-256: `12a6877535faec97844a8459d73dadef202aac969549c6e6a676a3b8584e7299`.
- Source archive SHA-256: `0904d16b61c85f674ff818a709482dad3bc7fb91c974403082c9824140cfb04d`.
- Build output: `dist/candidate-0.2.3/`.
- The candidate was installed alongside `qaos-docx-engine 0.1.2` and Pillow 13.0.0 in a clean CPython 3.11 environment; `pip check` passed and all 126 qaos-common tests passed. The full QAOS Engine clean install remains blocked by its `convert-csv-to-docx 0.1.0` dependency, which requires Pillow <13. This remains an unpublished candidate.

The immutable 0.2.2 release artifacts remain unchanged.
