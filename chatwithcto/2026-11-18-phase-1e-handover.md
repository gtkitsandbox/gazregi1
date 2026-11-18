# CTO handover — Phase 1E

Implemented historical intake for two verified London Gazette issues (Nos. 29002 and 29131): three page-provenanced records (appointment, promotion, appointment), two verified people, and one verified name variant. Added explicit historical-not-current wording, oldest-first person histories, extractor metadata overrides, scanned-page warnings and provenance tests. Original PDFs remain untracked and undeployed; no OCR was added. Curator documentation now covers operator-supplied identity mappings kept outside tracked data.

Validation: 14 Python tests passed; production build passed at 1,304 files, 7.82 MiB (largest 218.1 KiB), Pagefind 1,885.6 KiB across 666 files, 631 HTML pages, 630 sitemap URLs. Preview: 88 files, 0.95 MiB, 35/35 noindex, no sitemap or CNAME. Pagefind queries for both names, the variant, Indian Army and Gazette 29131 passed. Both Wrangler dry runs passed without authentication; local HTTP smoke tests returned 200 for historical pages and 404 for an unknown path.

Unresolved: corrections contact is unconfigured; Cloudflare authentication, custom-domain DNS and deployment were not performed; no browser or Playwright runtime was available, so browser smoke testing was skipped.

Implementation commit: `bd2bc47`
