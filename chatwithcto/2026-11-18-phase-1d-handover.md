# CTO handover — Phase 1D

## Implemented

21 configured countries; 15 with records. 240 records: 133 tenders, 12 grants, 62 public notices, 26 regulations, 7 appointments. Added Maldives (10 notices, 10 tenders, 4 appointments), 3 UK appointments, 4 Sri Lanka notices, 1 Japan tender. 7 verified people, 120 organisations.

Grants.gov records are grants; source and date-derived status are separate. Effective status: 119 open, 24 closed, 2 unknown; expired forecasts never open. Checksum scopes: 169 source response, 70 original source, 1 transformed snapshot.

Sri Lanka preserves 4 issues/193 pages. Official per-issue URLs unresolved: `documents.gov.lk` date pages are dynamic with no stable PDF link; none fabricated.

Isolated preview: 35 noindex pages, no sitemap/CNAME, separate Wrangler config; `noindex` documented as not access control.

## Validation

Production: 1,234 files, 7.39 MiB, largest 218.1 KiB; Pagefind 1,780 KiB / 630 files; 597 HTML, 596 sitemap URLs. Preview: 88 files, 0.95 MiB; Pagefind 669.3 KiB / 48 files. Builds, Pagefind, provenance, 8 tests, Wrangler dry runs and HTTP smoke passed. Browser tests skipped (no browser available).

## Incomplete

India, Indonesia, South Korea, Malaysia, Philippines, Thailand: zero records (access restrictions); Japan (1) and Sri Lanka (4) partial. No deployment or cloud authentication.

Implementation commit: `9df6e43`
