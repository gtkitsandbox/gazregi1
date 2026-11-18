# Phase 1B handover — Static Platform Foundation

- **Repository:** `gazregi1`
- **Production domain:** `gazetteregistry.com`
- **Commit:** `cd018f5522ab63c7a4543e2179f708a306ea4ec0`
- **Date:** 2026-11-18
- **Status:** Complete locally. Not pushed, not deployed.

## 1. Objective and outcome

Phase 1B converted the existing GazetteRegistry MVP into a static, country-independent public-records and procurement discovery platform. The original extraction output, Pagefind search, permanent `/records/<page-uid>/` URLs and SEO layer are preserved. New sections, curated record schemas, provenance enforcement, an isolated designer preview and a static Cloudflare configuration were added.

No records, statistics, customers or government affiliations were invented. All demonstration content lives under `demo/xx/` and is explicitly fictional.

## 2. Preserved behaviour

| Area | State |
| --- | --- |
| Existing extraction data | All 4 Sri Lanka issues and 193 pages still build. |
| Permanent record URLs | `/records/<page-uid>/` unchanged. |
| Official source text | `issue.json`, `pages.ndjson`, `text.jsonl.gz` retained unchanged. |
| Tracked source PDFs | All 4 files under `raw/` remain tracked and unmodified. |
| Pagefind search | Rebuilt and query-tested on every production and preview build. |
| GitHub Pages workflow | `.github/workflows/deploy.yml` unchanged and not triggered. |
| Existing SEO | Canonical URL, sitemap, robots, breadcrumbs and metadata retained and extended. |

`bluprint.md` was not modified.

## 3. Delivered structure

Generated sections:

- `/` — searchable home with honest empty states.
- `/gazettes/` and `/gazettes/<issue-id>/` — issue archive.
- `/records/<page-uid>/` — preserved page-level records.
- `/people/` and `/people/<cc>/<slug>/` — verified professional identities only.
- `/people/records/<uid>/` — appointment, commissioning, promotion and position records.
- `/organisations/` and `/organisations/<cc>/<slug>/`.
- `/tenders/` and `/tenders/<uid>/` — sector, location, organisation and closing-date filters.
- `/notices/`, `/regulations/` — indexes and detail pages.
- `/about/`, `/corrections/`, `404.html`, `sitemap.xml`, `robots.txt`, `CNAME`, `_headers`.

Reusable Jinja templates use shared macros for breadcrumbs, badges, verification status, empty states, record cards and source provenance. The UI is neutral and professional, with no external fonts, analytics or third-party scripts.

## 4. Architecture

```text
config/               site and preview configuration
data/<cc>/            country-independent production data
demo/xx/              isolated fictional preview data
src/content/          Pydantic models, loader, build orchestration
src/seo/              canonical URLs, metadata, breadcrumbs, JSON-LD, sitemap
src/templates/        Jinja2 pages and macros
src/assets/           CSS, JS, favicon
scripts/              extraction, build, validation, schemas, provenance
schemas/              generated JSON Schema
docs/                 curation and deployment guides
```

Country discovery is driven by `config/site.json` plus `data/<cc>/country.json`; templates contain no Sri Lanka-specific logic. URLs are built from country code, issue ID and record UID.

## 5. Data model and curation

Pydantic v2 models use `extra="forbid"` and are the single validation source. Nine JSON Schemas are generated into `schemas/`.

Curated records require:

- stable UID (`<CC>-<YEAR>-<GAZETTE>-<CATEGORY>-<SEQUENCE>`);
- an existing issue and PDF page;
- an exact printed-page match when supplied;
- a verbatim excerpt found in the extracted page text;
- known person/organisation references;
- type-specific appointment, tender, notice or regulation detail.

Record categories: `APPT`, `TEND`, `NOTC`, `REGL`.

Production data currently contains 0 curated records, 0 verified people and 0 organisations. The corresponding pages render honest empty states rather than fabricated content.

Full row shapes and review workflow: `docs/CURATION.md`.

## 6. Identity policy

- People are linked only through explicit `person_id`.
- Names alone never merge identities.
- Only `operator_verified` person entities and name variants are published, indexed and included in structured data.
- Unverified entities remain in NDJSON but generate no public page.
- Two verified people sharing a published name receive separate URLs and a cross-link disambiguation notice.
- `scripts/report_name_candidates.py` writes an advisory report to ignored `reports/`; it never edits or merges data.

The demonstration dataset exercises all of these paths, including two separate identities both named "A. Example".

## 7. Tender foundation

Tenders have a structured schema (reference, issuer, sector, location, closing date/time, optional document deadline and bid security), issuer organisation links, listing filters and source references. Filters operate client-side on generated cards, so the site remains static.

Not implemented, by instruction: payments, accounts, alerts, bid submission.

## 8. Storage, provenance and deployment limits

- Source registry: `data/<cc>/sources/sources.ndjson`, with SHA-256, byte size, issue mapping, optional verified official URL and check date.
- Registry currently covers the 4 existing PDFs.
- Builds verify the checksum when the local PDF is present and reject mismatches.
- New `raw/*.pdf` files are Git-ignored; existing tracked PDFs are preserved.
- Output directories `dist/` and `dist-preview/` are Git-ignored.
- No PDFs are copied into either output; production validation rejects PDFs.
- No R2, D1, KV, database, Rust/WASM or Worker runtime code was added.

## 9. Cloudflare configuration

`wrangler.jsonc` declares a static-assets deployment from `./dist` with `not_found_handling: "404-page"`. Wrangler is pinned to exact version `4.164.0`.

Commands:

```bash
npm run build          # production build + Pagefind + validation
npm run preview        # local wrangler dev against dist/
npm run validate       # revalidate existing dist/
npm run deploy         # operator-run wrangler deploy (not run)
```

No Cloudflare authentication, DNS change, R2/D1 provisioning or remote deployment was performed.

## 10. SEO and designer preview

Production pages have canonical URLs, descriptions, Open Graph/Twitter metadata, breadcrumbs, JSON-LD, one `h1` each, internal links and a sitemap. `robots.txt` allows crawling and references the sitemap.

The preview is a separate build (`npm run build:preview`) over `demo/xx/`, written to `dist-preview/`:

- `robots.txt` disallows all crawling;
- `_headers` adds `X-Robots-Tag: noindex`;
- every page carries `noindex`;
- no sitemap or `CNAME`;
- no production hostname, Sri Lanka markers, operator identity or internal infrastructure.

The preview search index contains only fictional demonstration records.

## 11. Actual validation results

Tool versions: Python 3.14.2, Node 24.22.2, Pagefind 1.5.2, Wrangler 4.164.0.

### Production — `npm run build` passed

```text
issues=4 pages=193 records=0 verified_people=0 organisations=0 html_files=207
assets: 444 files, 3.09 MiB
largest: dist/pagefind/pagefind-component-ui.js (171.4 KiB)
search index: 1169.4 KiB across 230 files
html: 207 pages (206 Pagefind bodies), jsonld: 207, noindex pages: 1
sitemap URLs: 206
search "2502": 24 result(s)
search "Gazette": 206 result(s)
```

### Designer preview — `npm run build:preview` passed

```text
issues=1 pages=2 records=7 verified_people=3 organisations=5 html_files=28
assets: 74 files, 0.86 MiB
largest: dist-preview/pagefind/pagefind-component-ui.js (171.4 KiB)
search index: 659.4 KiB across 41 files
html: 28 pages (27 Pagefind bodies), jsonld: 28, noindex pages: 28
search "office stationery": 7 result(s)
search "Example Procurement Authority": 6 result(s)
search "A. Example": 22 result(s)
search "Example Community Drainage Scheme": 7 result(s)
```

The same-name query returned results for both separate person identities; the validator confirms both person pages and the disambiguation notice.

### Additional checks

| Check | Result |
| --- | --- |
| Broken internal links / missing local assets | None |
| PDFs in generated output | None |
| Production demo-marker leakage | None |
| Preview production-marker leakage | None |
| Verified person pages and records rendered in HTML | Passed |
| Unverified person/variant publication | None |
| Schema export | 9 files generated |
| Source registry | 4 PDFs with SHA-256 |
| Name-candidate report (demo) | 2 advisory candidates, both identities retained, no merge |
| Name-candidate report (production) | 0 candidates |
| Local Wrangler `/` | HTTP 200 |
| Local Wrangler missing path | HTTP 404 with generated `404.html` |
| Local Wrangler `/pagefind/pagefind.js` | HTTP 200 |
| Wrangler `_headers` parsing | 1 valid rule |
| Git status after commit | Clean |

Cloudflare limits: 444 production files against the 20,000 hard limit and 15,000 target; largest file 171.4 KiB against the 25 MiB limit.

## 12. Commit

Commit `cd018f5522ab63c7a4543e2179f708a306ea4ec0` — "Build Phase 1B static platform foundation".

- 74 files changed, 7,746 insertions, 633 deletions.
- Local `main` is 1 commit ahead of `origin/main`.
- No push was performed.

## 13. Limitations and open items

1. `CLAUDE.md` is a 0-byte file; this handover follows the CTO instruction because no project-specific rules were available.
2. Production has no curated records, verified people or organisations yet. Discovery pages are functional but intentionally empty until acceptance data is curated.
3. No verified official PDF URLs are recorded (`official_url: null`); the site states this rather than guessing.
4. The corrections channel is disabled (`corrections_email: null`); `/corrections/` says so honestly.
5. Cloudflare was validated only with local `wrangler dev`; no remote preview, domain, TLS or DNS validation was possible without authentication.
6. Search validation runs Pagefind queries in Node against a local server, not a full browser end-to-end test.
7. Extracted text may contain OCR/layout artefacts; the official PDF remains authoritative.
8. When a source PDF is absent locally, checksum re-verification cannot run; the registry value remains recorded.
9. Tender filters are client-side and depend on JavaScript; core records and details remain static HTML.
10. The GitHub Pages workflow remains active but has not run for this commit.
11. The preview is non-indexable by configuration but should still not be deployed to a host where the operator does not control indexing headers.

## 14. Acceptance-testing workflow for historical gazettes

When the operator supplies historical gazettes:

1. Place each PDF in `raw/` using the existing `Gazette-YYYY-MM-DD-edition.pdf` convention. New PDFs are Git-ignored intentionally.
2. Extract with the verified official URL, if one exists:
   ```bash
   python scripts/extract_pdf.py raw/Gazette-YYYY-MM-DD-E.pdf --source-url <verified-url>
   ```
3. Refresh provenance:
   ```bash
   npm run sources
   ```
4. Curate people, organisations, variants and records following `docs/CURATION.md`. Use only verbatim source excerpts and exact page references.
5. Build and validate:
   ```bash
   npm run build
   ```
   Any excerpt, page, reference or identity error blocks the build.
6. Inspect locally:
   ```bash
   npm run preview
   ```
7. Commit only extraction output, the source registry and curated NDJSON. Do not commit newly added PDFs.

No operator identity is needed or recorded.
