# Sample Data Classification

Date: 2026-04-27

The tracked `sample company1/` and `sample company3 - LoneStar Plumbing/` document sets are approved synthetic development fixtures. They are used by parser and demo-flow tests to exercise realistic document formats without relying on seller-provided or customer-provided data.

These sample-company paths are excluded from Docker build contexts and new `sample company*` paths are ignored by git. Future fixtures that need to be committed should use explicitly sanitized data and should live under a clearly named fixture directory, such as `backend/tests/fixtures/`.
