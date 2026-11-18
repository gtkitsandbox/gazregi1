# GazetteRegistry

GazetteRegistry is an independent, file-first public-record and procurement discovery platform over official government gazettes and public-notice publications. Coverage is country-independent: Sri Lanka (`lk`) is one of 21 configured countries, not the site's organising principle.

The source of truth is local Python extraction output plus operator-curated NDJSON. Pagefind provides the prebuilt static search index. There is no database, runtime worker, account system or payment flow.

## What is generated

- `/` balanced international home page with Pagefind search.
- `/countries/` alphabetical, region-filterable coverage index and `/countries/<cc>/` country pages.
- `/gazettes/` and `/gazettes/<issue-id>/` issue archive for page-extracted gazettes.
- `/records/<page-uid>/` permanent page-level record URLs (preserved from the MVP).
- `/people/`, `/organisations/`, and person/organisation reference pages.
- `/people/records/<uid>/` appointment, commissioning, promotion and position records.
- `/tenders/` and `/tenders/<uid>/` with country, industry, location, organisation and closing-date filters.
- `/notices/` and `/notices/<uid>/`.
- `/regulations/` and `/regulations/<uid>/`.
- `/sources/` official source registry with access status, formats, languages, reuse terms and notes.
- `/about/`, `/corrections/`, `404.html`, `sitemap.xml`, `robots.txt`, `CNAME`.
- `/pagefind/` generated search index.

Only operator-verified people are published. A record is published only when its verbatim source excerpt is found in the stored extracted page text or retrieved document snapshot.

## Setup

```bash
python -m pip install -r requirements.txt
npm ci
```

## Commands

| Command | Purpose |
| --- | --- |
| `npm run build` | Build production `dist/`, Pagefind index, validate assets/SEO/links/provenance, then exercise Pagefind search. |
| `npm run build:site` | Build production HTML only (no Pagefind, no validation). |
| `npm run build:preview` | Build the isolated, non-indexable designer preview into `dist-preview/` with fictional multi-country demo records. |
| `npm run preview` | Start local Wrangler static preview against `dist/`. |
| `npm run preview:serve` | Serve `dist-preview/` locally without Wrangler. |
| `npm run validate` | Validate the existing `dist/` build and deployment limits. |
| `npm run validate:preview` | Validate the existing `dist-preview/` build. |
| `npm run validate:search` | Exercise the generated Pagefind index; add `--preview` for demo data. |
| `npm run package` | Rebuild production and preview, then write deterministic deployment ZIPs under `release/`. |
| `npm run ingest -- --country gb --all` | Run the registered source adapters for one country. |
| `npm run ingest -- --sync-registry` | Rewrite each country's source registry from `config/sources-intl.json`. |
| `npm run schemas` | Regenerate JSON Schema files from the Python models. |
| `npm run sources` | Refresh SHA-256 provenance for local PDFs in `raw/`. |
| `npm run deploy` | Deploy `dist/` with Wrangler (operator-run; not run automatically). |

Set `SITE_URL` for non-production canonical hosts:

```bash
SITE_URL=https://gazetteregistry.com npm run build
```

## Data layout

```text
config/
  site.json                 # site name, 20-country list, correction channel
  preview.json              # isolated designer-preview config (xx, yy, zz)
  sources-intl.json         # reusable international source registry definitions

data/<cc>/
  country.json              # country name, region, languages, coverage status
  <year>/<issue-dir>/       # page-extracted gazettes only (existing LK extraction)
    issue.json
    pages.ndjson
    text.jsonl.gz
  sources/sources.ndjson    # PDF checksums, issue mapping, official URL
  sources/documents.ndjson  # non-PDF source snapshots (HTML/XML/JSON/CSV text)
  sources/registry.ndjson   # source registry: formats, access, reuse, status
  entities/people.ndjson    # operator-verified person identities
  entities/organisations.ndjson
  entities/name-variants.ndjson
  records/records.ndjson    # structured appointments/tenders/notices/regulations

raw/                        # local PDF extraction inputs; not deployed
demo/                       # isolated fictional preview dataset (xx, yy, zz)
schemas/                    # generated JSON Schema
src/content/                # loader, build, models, SEO layer
src/ingest/                 # shared fetch/provenance layer and source adapters
src/templates/, src/assets/ # Jinja templates and static assets
scripts/                    # extraction, ingestion, build, validation, curation helpers
```

### Source provenance

There are two supported record-source forms:

1. **PDF gazette pages.** `issue.json` identifies the local source file and extraction method. `sources/sources.ndjson` records SHA-256 and byte length. The build verifies the checksum when the local PDF is present and rejects a registry mismatch. Records cite an exact PDF page and a verbatim excerpt from that page.
2. **HTML, XML, JSON, CSV and text sources.** An adapter retrieves the official publication, stores a text snapshot in `sources/documents.ndjson` with its SHA-256, byte count, official URL and retrieval date, then writes a record that cites the document. The build re-checks the excerpt against the snapshot and requires the record and snapshot checksums and URLs to agree.

Raw PDFs and retrieved source files are never copied into `dist/`. No adapter invents a title, reference, date or URL.

### Ingestion

`scripts/ingest.py` reads `config/sources-intl.json`, dispatches to `src/ingest/adapters.py`, and writes `records.ndjson`, `documents.ndjson` and `registry.ndjson` into the country directory. The same framework is used for every country; there is no per-country ingestion pipeline.

Adapters are deliberately selective. They skip personal notices, contact-person fields, e-mail addresses and private contact details. Procurement records omit bidder or official personal data. A source that is reachable but not machine-readable is recorded with its access status and notes rather than silently dropped.

### Curated records

Records are NDJSON with:

- a stable UID such as `GB-2026-NOTC-001`, `BD-2026-TEND-001` or `LK-2026-2502-APPT-001`;
- a `record_type` and either `issue_id` (PDF) or `publication_date` (non-PDF);
- a verbatim `source.excerpt` and either an exact `pdf_page` or a `document_id`;
- optional person/organisation identifiers and tender/regulation/notice details.

The build fails if an excerpt is absent from its cited text, page metadata disagrees, referenced entities are unknown, a non-PDF record's checksum or URL differs from its document snapshot, or a person reference lacks a position/organisation for appointment-type records. See [docs/CURATION.md](docs/CURATION.md).

### Identity policy

People are linked only through explicit `person_id` references. There is no automatic name-based merging. Unverified person entities and unverified name variants are held out of the public build. Two verified people with the same published name keep separate pages and link to a disambiguation notice. `python scripts/report_name_candidates.py` writes an advisory candidate report and never merges anything.

Organisations are created only when named as an issuing or buying organisation in an official source, with an explicit verification basis citing that source URL. No people were inferred from international procurement or notice data in this phase.

### Tender policy

Tenders are opportunities published by official sources. The site provides structured details, country/sector/closing-date filters and source references. It does not implement payments, accounts, alerts or bid submission. Closing dates and details must be verified with the issuing organisation.

## Deployment

- GitHub Pages workflow (`.github/workflows/deploy.yml`) remains active until an authorised cutover.
- Cloudflare deployment is static-only and configured in `wrangler.jsonc` from `dist/`. Wrangler is pinned to an exact version.
- `npm run preview` runs Wrangler locally; no remote authentication or deployment is performed by the build or validation scripts.
- `npm run package` writes `release/gazetteregistry-production.zip` and `release/gazetteregistry-preview.zip` for manual static upload. `release/` is ignored by Git. The production archive currently exceeds Cloudflare Pages direct-upload limits; it is compatible with Workers static assets and must not be trimmed to fit Pages.
- See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Coverage and limitations

- Fifteen of the 21 configured countries have published records: Australia, Bangladesh, Canada, Germany, Ireland, Japan, Kenya, Maldives, the Netherlands, New Zealand, Singapore, Sri Lanka, South Africa, the United Kingdom and the United States. India, Indonesia, South Korea, Malaysia, the Philippines and Thailand are configured but have no verified records; their pages show a truthful empty-coverage state.
- Coverage per country is uneven. Maldives meets the Phase 1D target of at least 10 notices and 10 procurement records; Japan and Sri Lanka have partial coverage. Exact counts are on `/countries/`.
- United Kingdom historical coverage includes verified 1914 and 1915 London Gazette issues with appointment and promotion records. Person pages label positions as historical records, not current employment.
- Some official sources are restricted, unavailable or not machine-readable. They remain visible on `/sources/` with notes; no records are fabricated for them.
- Extracted page and snapshot text can contain OCR/layout artefacts; the official source remains authoritative.
- Official URLs are shown only when recorded; they are never guessed.
- No operator identity or private personal data is published.
