# Phase 1C handover — International Data Foundation

- **Repository:** `gazregi1`
- **Production domain:** `gazetteregistry.com`
- **Baseline commit:** `cd018f5522ab63c7a4543e2179f708a306ea4ec0` (Phase 1B)
- **Commit:** local `main` HEAD created at the end of Phase 1C; hash supplied in the Phase 1C completion response.
- **Date:** 2026-11-18
- **Status:** Complete locally within the documented limits. Not pushed, not authenticated to Cloudflare, not deployed.

## 1. Objective and outcome

Phase 1C extended the accepted Phase 1B static platform with a source registry, a reusable ingestion layer, non-PDF provenance, international country discovery and genuine public records from official sources.

Delivered:

- 20 configured countries with region and coverage status.
- 43 registered sources across those countries, each with source organisation, publication type, official URL, formats, languages, access method, access status and reuse restrictions.
- 213 curated public records from genuine official sources: 51 public notices, 136 procurement opportunities and 26 regulations.
- 238 source-document snapshots with SHA-256 checksums and retrieval metadata.
- Country and region navigation, country-specific counts, global search and tender filters.
- Multi-country fictional preview isolation.
- No invented records or source URLs.

Coverage is **incomplete against the Phase 1C target** of approximately 10 verified public notices and 10 procurement records per country. The actual position is reported in section 5. No source was fabricated to close the gap.

## 2. Preserved Phase 1B behaviour

| Area | State |
| --- | --- |
| Sri Lanka extraction data | All 4 gazette issues and 193 extracted pages still build. |
| Permanent page URLs | `/records/<page-uid>/` unchanged. All 193 record pages generated. |
| Sri Lanka source data | `issue.json`, `pages.ndjson`, `text.jsonl.gz` and the 4 tracked PDFs unchanged. |
| Pagefind search | Rebuilt; real query validation passed. |
| SEO | Canonical URLs, sitemap, robots, breadcrumbs, JSON-LD and metadata retained and extended. |
| GitHub Pages workflow | `.github/workflows/deploy.yml` unchanged and not triggered. |
| Static deployment configuration | `wrangler.jsonc` and static asset routing unchanged. |
| Existing identity rules | No automatic identity merging; verified publication policy retained. |
| `bluprint.md` | Not modified. |

No Sri Lanka-specific preference was added. Homepage ordering rotates one latest record per country; country pages and search are global and alphabetical/alphabetical-by-region.

## 3. Delivery summary

### 3.1 Ingestion architecture

New reusable layer:

```text
src/ingest/core.py       fetch, checksum, date parsing, document/record drafts, PII scrubbing
src/ingest/adapters.py   source-specific adapters (API, feed, HTML, CSV, gazette)
scripts/ingest.py        CLI: --country, --source, --limit, --all, --sync-registry
config/sources-intl.json 43 source definitions used to seed the registry
data/<cc>/sources/       documents.ndjson and registry.ndjson
data/<cc>/records/       records.ndjson
data/<cc>/entities/      organisations.ndjson
```

There is one ingestion layer and one record shape for all countries. No per-country duplicate pipeline was created.

Adapters delivered for:

- Australia: Federal Register of Legislation (OData titles API), notifiable instruments.
- Bangladesh: e-GP tender servlet and detail pages.
- Canada: Canada Gazette Part I; CanadaBuys CSV.
- Germany: BGBl; TED API v3.
- Ireland: TED API v3.
- Kenya: PPIP tender listing.
- Netherlands: TED API v3.
- New Zealand: GETS tender listing.
- Singapore: GeBIZ opportunity listing.
- South Africa: eTenders DataTables endpoint.
- United Kingdom: The Gazette notice pages; Find a Tender OCDS release packages.
- United States: Federal Register API; Grants.gov search2/fetchOpportunity.

### 3.2 Provenance and schema

- `SourceRegistryEntry` and `SourceDocumentSnapshot` models added; JSON Schemas regenerated as `schemas/source-registry.schema.json` and `schemas/source-document.schema.json`.
- `RecordSource.kind` now supports `pdf`, `html`, `xml`, `json`, `csv` and `text`.
- PDF records continue to require `pdf_page` and an issue bundle.
- Non-PDF records require `document_id`, a snapshot, an official URL and a registry source.
- Excerpts are validated against extracted PDF text or the stored source-document text at build time.
- Each non-PDF record links to `/sources/#source-<document-id>` and the original official URL.
- Each PDF record retains its issue bundle, page number, printed page and checksum.
- No source PDFs or source documents are copied into `dist/`.
- A shared `Origin` view lets every template render either provenance form without country-specific logic.

### 3.3 Public surfaces

- `/` — balanced latest records, alphabetical country grid, coverage counts, global search.
- `/countries/` — all 20 countries, alphabetical, region and coverage filters.
- `/countries/<cc>/` — country profile, source summary, record counts and country-filtered lists.
- `/sources/` — source registry with country/status filters, official links, formats, languages, access method and reuse notes.
- `/notices/`, `/regulations/`, `/tenders/` — global indexes with country filters; tender status and closing-state filters.
- Existing `/people/`, `/organisations/`, `/gazettes/`, `/records/<page-uid>/`, `/about/` and `/corrections/` retained.

### 3.4 Identity and privacy

- No person records were added in Phase 1C. Production person count remains 0.
- Organisations are created only from source-published buyer/issuer names, with per-country slug identity. No person-name merging was performed.
- The existing operator verification and publication-review policy is unchanged.
- Contact details in retrieved HTML are redacted before snapshots are stored. The final scan found no email addresses, phone numbers or private contact lines in production snapshots.
- Adapters skip records whose source content is primarily a private individual's contact, insolvency, disqualification or estate notice.
- No unnecessary personal identifiers were added.

### 3.5 Preview isolation

- Fictional preview now covers `xx`, `yy` and `zz`.
- `yy` (Nordmark) and `zz` (Coralia) each have country configuration, a fictional organisation, a tender/notice, snapshots and registry entries.
- All preview pages are `noindex`; no sitemap URLs are emitted.
- Production builds contain no Nordmark, Coralia, `DEMO-YY-001` or `example.invalid` markers; the validator checks this.
- Preview builds contain no production source text or operator information.

## 4. Source registry

43 sources registered:

| Access status | Count | Meaning |
| --- | ---: | --- |
| Verified | 23 | Endpoint/page checked and used, or checked and confirmed reachable. |
| Restricted | 11 | Bot protection, HTTP 403, rate limiting, TLS failure or no stable listing. |
| Unavailable | 3 | Empty/timeout responses. |
| Planned | 6 | Registered coverage intent; not probed in Phase 1C. |

Registered formats include HTML, XML, JSON, CSV, PDF, RSS, Atom, OData and SRU. Media type is recorded on each snapshot.

### 4.1 Verified sources

| Source ID | Country | Records ingested | Source |
| --- | --- | ---: | --- |
| `au-legislation-notices` | AU | 9 | Federal Register of Legislation — notifiable instruments |
| `au-legislation-register` | AU | 22 | Federal Register of Legislation titles API |
| `bd-egp` | BD | 26 | National e-Government Procurement (e-GP) portal |
| `ca-canada-gazette` | CA | 12 | Canada Gazette, Part I |
| `ca-canadabuys` | CA | 4 | CanadaBuys tender notices open data |
| `de-bgbl` | DE | 5 | Bundesgesetzblatt |
| `de-ted` | DE | 12 | Tenders Electronic Daily |
| `gb-find-a-tender` | GB | 12 | Find a Tender service |
| `gb-the-gazette` | GB | 11 | The Gazette (UK official public record) |
| `id-jdih` | ID | 0 | JDIH legal documentation network |
| `ie-iris-oifigiuil` | IE | 0 | Iris Oifigiúil |
| `ie-irish-statute-book` | IE | 0 | Irish Statute Book |
| `ie-ted` | IE | 12 | Tenders Electronic Daily |
| `jp-kanpo` | JP | 0 | Kanpō |
| `ke-ppip` | KE | 12 | Public Procurement Information Portal |
| `my-lom` | MY | 0 | Laws of Malaysia |
| `nl-ted` | NL | 12 | Tenders Electronic Daily |
| `nz-gets` | NZ | 12 | Government Electronic Tender Service |
| `sg-gebiz` | SG | 10 | GeBIZ opportunities |
| `us-federal-register` | US | 18 | Federal Register documents API |
| `us-grants-gov` | US | 12 | Grants.gov opportunity APIs |
| `us-usaspending` | US | 0 | USAspending award data API |
| `za-etenders` | ZA | 12 | eTenders portal |

Sources with zero ingested records were verified as reachable but did not yield extractable records in Phase 1C:

- `id-jdih`: legal-document index reachable, but no suitable recent structured record set was ingested.
- `ie-iris-oifigiuil` and `ie-irish-statute-book`: reachable, but no records selected; Irish procurement records came from TED.
- `jp-kanpo`: daily index reachable, but article pages are JavaScript PDF viewers; no HTML extraction path was completed.
- `my-lom`: reachable, but no suitable record set was extracted.
- `us-usaspending`: API reachable; no award records were ingested.

### 4.2 Restricted and unavailable sources

| Source ID | Country | Status | Official URL | Recorded reason |
| --- | --- | --- | --- | --- |
| `au-austender` | AU | Restricted | https://www.tenders.gov.au/ | HTTP 403 on automated requests. |
| `in-cppp` | IN | Restricted | https://eprocure.gov.in/cppp/ | Internal API rejected guessed payloads; no public feed found. |
| `in-egazette` | IN | Restricted | https://egazette.gov.in/ | Connections reset or required insecure TLS workarounds. |
| `ke-kenyalaw` | KE | Restricted | https://www.kenyalaw.org/ | Gazette endpoints returned HTTP 403. |
| `nl-oep` | NL | Restricted | https://zoek.officielebekendmakingen.nl/ | SRU endpoint returned HTTP 429/500 after an initial response. |
| `nz-gazette` | NZ | Restricted | https://gazette.govt.nz/ | Search endpoint returned an Incapsula challenge. |
| `ph-official-gazette` | PH | Restricted | https://www.officialgazette.gov.ph/ | HTTP 403. |
| `ph-philgeps` | PH | Restricted | https://www.philgeps.gov.ph/ | Portal timed out. |
| `sg-sso` | SG | Restricted | https://www.sso.agc.gov.sg/ | API returned empty responses. |
| `th-royal-gazette` | TH | Restricted | https://ratchakitcha.soc.go.th/ | HTTP 403. |
| `za-gpw` | ZA | Restricted | https://www.gpwonline.co.za/ | Category pages publish no static links to individual gazettes. |
| `kr-gwanbo` | KR | Unavailable | https://www.gwanbo.go.kr/ | Empty response body. |
| `lk-documents` | LK | Unavailable | https://www.documents.gov.lk/ | Site did not respond; existing 4 tracked gazettes remain the verified basis. |
| `lk-procurement` | LK | Unavailable | https://www.procurement.gov.lk/ | Site did not respond; no procurement records ingested. |

Planned-only sources: `bd-bgpress`, `id-lkpp`, `jp-p-portal`, `kr-narajangteo`, `my-eperolehan`, `th-gprocurement`.

## 5. Actual country coverage

Record counts are actual generated records, not targets. Source counts show verified/registered.

| Country | Region | Status | Notices | Tenders | Regulations | Total | Sources | Documents |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Australia (AU) | Oceania | Partial | 10 | 0 | 21 | 31 | 2/3 | 28 |
| Bangladesh (BD) | South Asia | Partial | 0 | 26 | 0 | 26 | 1/2 | 27 |
| Canada (CA) | North America | Partial | 12 | 4 | 0 | 16 | 2/2 | 27 |
| Germany (DE) | Europe | Partial | 0 | 12 | 5 | 17 | 2/2 | 17 |
| United Kingdom (GB) | Europe | Partial | 11 | 12 | 0 | 23 | 2/2 | 40 |
| Indonesia (ID) | Southeast Asia | Planned | 0 | 0 | 0 | 0 | 1/2 | 0 |
| Ireland (IE) | Europe | Partial | 0 | 12 | 0 | 12 | 3/3 | 12 |
| India (IN) | South Asia | Planned | 0 | 0 | 0 | 0 | 0/2 | 0 |
| Japan (JP) | East Asia | Planned | 0 | 0 | 0 | 0 | 1/2 | 0 |
| Kenya (KE) | Africa | Partial | 0 | 12 | 0 | 12 | 1/2 | 10 |
| South Korea (KR) | East Asia | Planned | 0 | 0 | 0 | 0 | 0/2 | 0 |
| Sri Lanka (LK) | South Asia | Verified | 0 | 0 | 0 | 0 | 0/2 | 0 |
| Malaysia (MY) | Southeast Asia | Planned | 0 | 0 | 0 | 0 | 1/2 | 0 |
| Netherlands (NL) | Europe | Partial | 0 | 12 | 0 | 12 | 1/2 | 12 |
| New Zealand (NZ) | Oceania | Partial | 0 | 12 | 0 | 12 | 1/2 | 12 |
| Philippines (PH) | Southeast Asia | Planned | 0 | 0 | 0 | 0 | 0/2 | 0 |
| Singapore (SG) | Southeast Asia | Partial | 0 | 10 | 0 | 10 | 1/2 | 10 |
| Thailand (TH) | Southeast Asia | Planned | 0 | 0 | 0 | 0 | 0/2 | 0 |
| United States (US) | North America | Partial | 18 | 12 | 0 | 30 | 3/3 | 31 |
| South Africa (ZA) | Africa | Partial | 0 | 12 | 0 | 12 | 1/2 | 12 |
| **Total** | | | **51** | **136** | **26** | **213** | **23/43** | **238** |

### 5.1 Coverage assessment against the Phase 1C target

- Target for 20 countries: approximately 200 notices and 200 procurement records.
- Delivered: 51 notices and 136 tender/procurement records, plus 26 regulations.
- Only 12 of 20 countries have any curated record.
- 8 countries have zero records: ID, IN, JP, KR, LK, MY, PH, TH.
- 0 appointment records, 0 named-company notices beyond official gazette/register notices, and 0 award records were ingested.
- 0 person records were created.
- Sri Lanka has 4 issues and 193 extracted gazette pages preserved, but 0 curated records and 0 procurement records in Phase 1C. Its two source endpoints were unavailable.
- The shortfall is due to source access restrictions, JavaScript-only article viewers, missing stable listing endpoints, and the decision not to fabricate records. It is not presented as complete coverage.

## 6. Validation results

### 6.1 Production build

Command: `npm run build`

| Check | Result |
| --- | --- |
| Python build | Passed |
| Pagefind indexing | 540 pages indexed |
| Site validator | Passed |
| Search validator | Passed |
| Files | 1,121 |
| Total size | 6.72 MiB |
| HTML pages | 541 (540 Pagefind bodies) |
| JSON-LD pages | 541 |
| Noindex pages in production | 1 (`404.html`) |
| Sitemap URLs | 540 |
| Search index | 1,678.3 KiB across 573 files |
| Largest file | `dist/tenders/index.html`, 193.1 KiB |
| PDFs in output | None |
| Broken internal links / missing assets | None reported |
| Sri Lanka issue pages | 4 |
| Sri Lanka record pages | 193 |
| Country pages | 20 |

Search queries exercised against the real Pagefind index:

| Query | Results |
| --- | ---: |
| `2502` | 24 |
| `Gazette` | 481 |
| `Seelotsenausbildung` | 2 |
| `UCDOPP5639` | 4 |
| `NETWORK EQUIPMENT AND SMART BOARDROOMS` | 3 |
| `United Kingdom` | 7 |
| `1374249` | 3 |

All queries returned the expected country, source or record page.

Validator checks included: country page existence and naming; per-country record counts in HTML; source anchors for non-PDF records; official URL and checksum presence; country consistency between record, document and registry; sitemap/canonical/JSON-LD presence; demo-marker isolation; and schema-required fields.

### 6.2 Preview build

Command: `npm run build:preview`

| Check | Result |
| --- | --- |
| Build and Pagefind | Passed |
| Site validator | Passed |
| Search validator | Passed |
| Files | 88 |
| Total size | 0.94 MiB |
| HTML pages | 35, all noindex |
| Sitemap URLs | 0 |
| Search index | 668.9 KiB across 48 files |
| Nordmark / Coralia | Present |
| Production source text | None found |
| Production demo markers | None found |

Preview search checks passed for `office stationery`, `Example Procurement Authority`, `A. Example` (both separate identities), `Example Community Drainage Scheme`, `DEMO-YY-001`, `Nordmark` and `Coralia`.

### 6.3 Local static-server checks

Wrangler 4.164.0 was run only with local static-asset serving, not authenticated.

| Route | Result |
| --- | --- |
| `/` | HTTP 200 |
| Unknown path | HTTP 404 with generated `404.html` |
| `/pagefind/pagefind.js` | HTTP 200 |
| `/sources/` | HTTP 200 |
| `/countries/bd/` | HTTP 200 |

### 6.4 Resource usage

| Item | Value |
| --- | ---: |
| Generated production files | 1,121 |
| Generated production size | 6.72 MiB |
| Generated preview files | 88 |
| Generated preview size | 0.94 MiB |
| Production data directory | 1.6 MiB |
| Demo data directory | 132 KiB |
| Engineering target | 15,000 files |
| Cloudflare hard limit | 20,000 files |
| Largest generated file | 193.1 KiB (limit 25 MiB) |

## 7. Schemas and validation behaviour

Regenerated schemas:

- `schemas/country.schema.json`
- `schemas/record.schema.json`
- `schemas/source-document.schema.json`
- `schemas/source-registry.schema.json`
- Existing person, organisation, issue and source schemas remain.

Key rules:

- PDF records still require an issue, page UID, PDF page and excerpt match.
- Non-PDF records require a document ID, official URL, registry source and excerpt match against the stored snapshot.
- Non-PDF ingestion is not blocked by PDF page requirements.
- Official URLs are never synthesised; they come from the source response or a documented official pattern recorded by the adapter.
- Build fails on provenance, excerpt, identity or date inconsistencies.

## 8. Demo isolation

- `demo/yy/` — fictional Nordmark; one procurement record; fictional registry and snapshot.
- `demo/zz/` — fictional Coralia; one public notice; fictional registry and snapshot.
- `demo/xx/` — retained Phase 1B fictional records and separate identities.
- Preview configuration uses `xx`, `yy`, `zz` only.
- No demo data is loaded into production builds.
- Production validator checks for all demo names, IDs and invalid domains.
- Preview validator checks that demo content is present.
- Preview has no sitemap, all pages are noindex, and no operator or internal documentation is published.

## 9. Constraints observed

- No R2, D1, KV, database, Rust, WASM or Worker runtime functionality added.
- No Cloudflare authentication, DNS change, remote preview or remote deployment.
- No bulk PDF commits; no new PDFs committed.
- Existing static deployment configuration maintained.
- Generated assets remain below the 15,000-file target.
- Local commit only; no push.
- No records or source URLs fabricated.
- No automatic person-identity merging.
- No Sri Lanka or other country preference.
- No internal docs or operator information in the demo.

## 10. Known limitations and open items

1. `CLAUDE.md` is still a 0-byte file. The corrected instruction referenced by the CTO was not present in the repository; this handover follows the Phase 1B handover structure and the Phase 1C instruction.
2. Coverage is materially below target: 213 records total, 12 of 20 countries populated, 8 countries empty. See section 5.
3. No award records and no appointment records were curated. Tender statuses are recorded as 119 open and 17 closed; these are source states at retrieval time, not live states.
4. No production person records exist. Identity verification and non-merging rules therefore had no production person cases to exercise in Phase 1C; the demo retains the two separate `A. Example` identities.
5. Sources marked `verified` may still yield zero records where extraction was impractical (notably ID, JP and MY).
6. Restricted and unavailable sources remain unresolved; see section 4.2. They are surfaced honestly on `/sources/`.
7. Sri Lanka's gazette and procurement endpoints were unavailable. The four existing gazettes and 193 pages remain the only verified Sri Lanka basis; no official source URL was invented for them.
8. TED records use the publication date returned in the source. All stored documents have a non-null source publication date; no retrieval-date fallback was used in the final data.
9. Search validation runs Pagefind in Node against a local static server; it is not a full browser end-to-end test.
10. Tender closing-state filters are client-side and depend on JavaScript. Tender detail and index content remain static HTML.
11. Local Wrangler validation covered static routes only. No Cloudflare account, remote preview, TLS or DNS validation was performed.
12. The GitHub Pages workflow remains active but has not run for this commit.
13. `CLAUDE.md` being empty means no project-specific handover format could be applied beyond the prior Phase 1B convention.
14. Some multilingual source text is preserved verbatim (German, Dutch, Bengali, Japanese, Korean, Thai, Sinhala, Tamil and others appear in registry metadata or source text). Unicode is preserved; no transliteration or translation was added.
15. Source registry entries record access status as at 2026-11-18; publishers can change access controls without notice.

## 11. Commands

```bash
npm run build              # production build + Pagefind + validation
npm run build:preview      # isolated fictional preview
npm run validate           # production structural validation
npm run validate:search    # Pagefind query checks
npm run ingest -- --all    # run all registered adapters
npm run ingest -- --country gb --limit 10
npm run schemas            # regenerate JSON Schemas
```

The ingestion CLI writes NDJSON only. It does not deploy, upload PDFs or call Cloudflare APIs.

## 12. Commit

One local commit was created on `main` containing the Phase 1C source, configuration, data, schemas, templates, documentation and this handover.

- No push.
- No tag.
- No remote deployment.
- No Cloudflare authentication.
- Working tree clean after commit.

The commit hash is returned in the Phase 1C completion response.
