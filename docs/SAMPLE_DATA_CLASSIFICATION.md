# Sample Data Classification

Date: 2026-04-27

The tracked `backend/tests/fixtures/peakair/` document set is an approved synthetic development fixture used by parser tests to exercise realistic document formats without relying on seller-provided or customer-provided data.

`sample company3 - LoneStar Plumbing/` was removed from the repository. It was synthetic and unused by tests. Root-level sample-company paths stay gitignored.

Runtime analysis output (`Company4artifacts/`, `.artifacts/`, and `uploads/`) is gitignored and must not be committed. Future fixtures that need to be committed should use explicitly sanitized data and should live under a clearly named fixture directory, such as `backend/tests/fixtures/`.
