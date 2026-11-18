# GazetteRegistry

GazetteRegistry is an independent, file-first public-record and procurement discovery platform over official government Gazette publications. Sri Lanka (`lk`) is the initial country; the data and URL architecture is country-independent.

The source of truth is local Python extraction output plus operator-curated NDJSON. Pagefind provides the prebuilt static search index. There is no database, runtime worker, account system or payment flow.

## What is generated

- `/` searchable home page with Pagefind.
- `/gazettes/` and `/gazettes/<issue-id>/` issue archive.
- `/records/<page-uid>/` permanent page-level record URLs (preserved from the MVP).
- `/people/`, `/organisations/`, and person/organisation reference pages.
- `/people/records/<uid>/` appointment, commissioning, promotion and position records.
- `/tenders/` and `/tenders/<uid>/` with industry, location, organisation and closing-date filters.
- `/notices/` and `/notices/<uid>/`.
- `/regulations/` and `/regulations/<uid>/`.
- `/about/`, `/corrections/`, `404.html`, `sitemap.xml`, `robots.txt`, `CNAME`.
- `/pagefind/` generated search index.

Only operator-verified people are published. Records are published only when their verbatim source excerpt is found in the extracted page text.

## Setup

```bash
python -m pip install -r requirements.txt
npm ci
```

## Commands

| Command | Purpose |
| --- | --- |
| `npm run build` | Build production `dist/`, Pagefind index, validate assets/SEO/links, then exercise Pagefind search. |
| `npm run build:site` | Build production HTML only (no Pagefind, no validation). |
| `npm run build:preview` | Build the isolated, non-indexable designer preview into `dist-preview/` with fictional demo records. |
| `npm run preview` | Start local Wrangler static preview against `dist/`. |
| `npm run preview:serve` | Serve `dist-preview/` locally without Wrangler. |
| `npm run validate` | Validate the existing `dist/` build and deployment limits. |
| `npm run validate:preview` | Validate the existing `dist-preview/` build. |
| `npm run validate:search` | Exercise the generated Pagefind index; add `--preview` for demo data. |
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
  site.json                 # site name, countries, correction channel
  preview.json              # isolated designer-preview config

data/lk/
  country.json              # country name, languages, Gazette title
  <year>/<issue-dir>/
    issue.json              # issue metadata (existing extraction)
    pages.ndjson            # page-level records (existing extraction)
    text.jsonl.gz           # compressed extracted text (existing extraction)
  sources/sources.ndjson    # PDF checksums, issue mapping, official URL
  entities/people.ndjson    # operator-verified person identities
  entities/organisations.ndjson
  entities/name-variants.ndjson
  records/records.ndjson    # structured appointment/tender/notice/regulation records

raw/                        # local PDF extraction inputs; not deployed
demo/                       # isolated fictional preview dataset (XX)
schemas/                    # generated JSON Schema
src/                        # Python content/SEO layer, Jinja templates, assets
scripts/                    # extraction, build, validation, curation helpers
```

### Source provenance

`issue.json` identifies the local source file and extraction method. `data/<country>/sources/sources.ndjson` records SHA-256 and byte length. Builds verify the checksum when the local PDF is present and reject a registry mismatch. Raw PDFs are never copied into `dist/`.

New PDFs under `raw/` are ignored by Git. Existing tracked source documents are preserved. Run `npm run sources` after adding a local PDF and extracting it.

### Curated records

Records are hand-curated NDJSON with:

- a stable UID such as `LK-2026-2502-APPT-001`;
- a `record_type` and issue reference;
- a verbatim `source.excerpt`, exact `pdf_page` and optional `printed_page`;
- optional person/organisation identifiers and tender/regulation/notice details.

The build fails if the excerpt is not present on the cited extracted page, the printed page disagrees, referenced entities are unknown, or a person reference lacks a position/organisation for appointment-type records. See [docs/CURATION.md](docs/CURATION.md).

### Identity policy

People are linked only through explicit `person_id` references. There is no automatic name-based merging. Unverified person entities and unverified name variants are held out of the public build. Two verified people with the same published name keep separate pages and link to a disambiguation notice. `python scripts/report_name_candidates.py` writes an advisory candidate report and never merges anything.

### Tender policy

Tenders are opportunities published in official Gazettes. The site provides structured details, filters and source references. It does not implement payments, accounts, alerts or bid submission. Closing dates and details must be verified with the issuing organisation.

## Deployment

- GitHub Pages workflow (`.github/workflows/deploy.yml`) remains active until an authorised cutover.
- Cloudflare deployment is static-only and configured in `wrangler.jsonc` from `dist/`. Wrangler is pinned to an exact version.
- `npm run preview` runs Wrangler locally; no remote authentication or deployment is performed by the build or validation scripts.
- See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Limitations

- Extracted page text can contain OCR/layout artefacts; the official PDF remains authoritative.
- Notice-level records are curated, not generated automatically. Pages without curated records remain searchable as page records.
- Official PDF URLs are shown only when recorded; they are never guessed.
- No operator identity or private personal data is published.
