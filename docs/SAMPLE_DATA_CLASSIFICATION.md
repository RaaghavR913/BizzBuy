# Sample Data Classification

Date: 2026-04-27

The tracked `backend/tests/fixtures/peakair/` document set is an approved synthetic development fixture used by parser tests to exercise realistic document formats without relying on seller-provided or customer-provided data.

The tracked `sample company3 - LoneStar Plumbing/` document set is also synthetic, but it is not currently referenced by automated tests. Keep or remove it based on product/demo needs.

Root-level sample-company paths are excluded from Docker build contexts, and new `sample company*` paths are ignored by git. Future fixtures that need to be committed should use explicitly sanitized data and should live under a clearly named fixture directory, such as `backend/tests/fixtures/`.
