# Curating records and identities

All examples in this document are fictional. Do not copy demonstration names or values into production data.

## 1. Prerequisites

There are two supported ways to add records.

### PDF gazette pages

1. Extract the official PDF into `data/<country>/<year>/<issue-dir>/` with `scripts/extract_pdf.py`.
2. Refresh provenance with `npm run sources`.
3. Add curated rows to the country's `records/records.ndjson`.
4. Run `npm run build`. The build rejects unsupported records before publishing anything.

A PDF record requires:

- `issue_id` that already exists;
- `source.kind` of `pdf` (or omitted);
- `source.pdf_page` that exists in `pages.ndjson`;
- `source.printed_page` matching the extracted page if supplied;
- `source.excerpt` copied verbatim from that page's extracted text;
- a stable UID beginning `<issue_id>-<CATEGORY>-`, where category is `APPT`, `TEND`, `NOTC` or `REGL` (for example `LK-2026-2502-NOTC-001`).

### HTML, XML, JSON, CSV or text sources

1. Confirm the publisher and official URL are described in `config/sources-intl.json`.
2. Ingest with an adapter: `npm run ingest -- --country <cc> --source <source-id> --limit 10`.
3. The adapter writes a text snapshot to `data/<cc>/sources/documents.ndjson`, a registry row to `sources/registry.ndjson`, and records to `records/records.ndjson`.
4. Run `npm run build`.

A non-PDF record requires:

- `source.kind` of `html`, `xml`, `json`, `csv` or `text`;
- `source.document_id` identifying a snapshot in `sources/documents.ndjson`;
- `publication_date` on the record (the document date may be used as a fallback only when the record date is genuinely unknown);
- `source.official_url` and `source.sha256` matching the snapshot exactly;
- `source.excerpt` present verbatim in the snapshot text;
- the snapshot's `source_id` present in the country's source registry.

PDF page numbers are forbidden on non-PDF records, and `issue_id` is forbidden. This keeps the permanent URL and provenance rules intact without forcing every country through PDF extraction.

Whitespace is normalised before either excerpt check, but the words and order must match. If a PDF has a malformed text layer, correct the extraction or choose a shorter verbatim excerpt; do not paraphrase the excerpt.

### Importing operator-supplied historical PDFs

For a batch of historical gazettes supplied out of band:

1. Place each original PDF in `raw/` (Git-ignored) and record its filename, publisher, issue number, publication date and acquisition note outside the public build.
2. Extract with explicit metadata when the filename does not follow `Gazette-YYYY-MM-DD-edition.pdf`:

   ```bash
   python scripts/extract_pdf.py raw/<file>.pdf --country <cc> \
     --gazette-number <number> --publication-date YYYY-MM-DD \
     --edition <code> --gazette-type regular|extraordinary|supplement \
     --language <code> [--source-url <verified-url>]
   ```

   Only pass `--source-url` when the official URL was independently verified. `--gazette-number` and dates must be copied from the document or an authoritative publisher listing.
3. Check the extracted page count and printed page labels against the PDF. A warning lists pages without a text layer. Scanned-only documents fail with `OCR is not enabled`; supply a text-layer PDF, OCR the file outside this repository, or transcribe the relevant notice manually. No OCR engine is bundled.
4. Run `npm run sources` to record the PDF checksum and issue mapping in tracked `sources/sources.ndjson`. The PDF itself remains untracked.
5. Add one record per notice with a verbatim excerpt, the exact `pdf_page` and a stable `<issue_id>-<CATEGORY>-<NNN>` UID. Use `appointment`, `commissioning`, `promotion`, `professional_position` or `organisational_appointment` according to the printed notice, not a generic label.
6. Run `npm test` and `npm run build`. Provenance failures name the record and page; fix the extraction or excerpt, never the source text.
7. Keep original PDFs out of `dist/` and out of Git unless redistribution rights are confirmed.

For a reusable batch, adapt `scripts/import_historical_records.py`: it asserts each excerpt against the extracted page before writing records, people, organisations and verified name variants. It never guesses a person's identity from a name alone.

No automated importer guesses issue numbers, dates or official URLs. Those values must come from the document itself or an authoritative publisher listing.

## 2. Record types

| `record_type` | Category code | Required detail |
| --- | --- | --- |
| `appointment` | APPT | people with position + organisation |
| `commissioning` | APPT | people with position + organisation |
| `promotion` | APPT | people with position + organisation |
| `professional_position` | APPT | people with position + organisation |
| `organisational_appointment` | APPT | people with position + organisation |
| `tender` | TEND | `tender` object |
| `public_notice` | NOTC | `notice` object |
| `regulation` | REGL | `regulation` object |

### 2.1 Appointment example (fictional)

```json
{
  "uid": "XX-2099-9999-APPT-001",
  "record_type": "appointment",
  "title": "Appointment of Chairperson, Example Authority",
  "summary": null,
  "issue_id": "XX-2099-9999",
  "people": [
    {
      "person_id": "person:xx:a-example-001",
      "published_name": "A. Example",
      "position": "Chairperson",
      "position_kind": "appointment",
      "organisation_ids": ["org:xx:example-authority"]
    }
  ],
  "organisation_ids": ["org:xx:example-authority"],
  "location": "Sample District",
  "keywords": ["appointment"],
  "source": {
    "pdf_page": 2,
    "printed_page": 2,
    "excerpt": "A. Example has been appointed Chairperson of the Example Authority with effect from 1 January 2099."
  }
}
```

`published_name` is exactly what the notice printed. It may differ from the verified canonical name; the person page shows both transparently. Do not add a biography, address, age, family relationship or inferred role.

### 2.2 Tender example (fictional)

```json
{
  "uid": "XX-2099-9999-TEND-001",
  "record_type": "tender",
  "title": "Supply of office stationery",
  "issue_id": "XX-2099-9999",
  "organisation_ids": ["org:xx:example-procurement-authority"],
  "location": "Sample District",
  "keywords": ["stationery", "supply"],
  "tender": {
    "reference": "DEMO/TEND/2099/001",
    "issuer_organisation_id": "org:xx:example-procurement-authority",
    "sector": "goods",
    "location": "Sample District",
    "closing_date": "2099-02-15",
    "closing_time": "14:00",
    "document_deadline": null,
    "bid_security_lkr": 250000
  },
  "source": {
    "pdf_page": 1,
    "printed_page": 1,
    "excerpt": "The Example Procurement Authority invites sealed bids for the supply of office stationery. Tender reference DEMO/TEND/2099/001. Bids close on 15 February 2099 at 14:00. Bid security: LKR 250,000."
  }
}
```

Sectors: `civil_works`, `goods`, `consultancy`, `services`, `it`, `maintenance`, `auction`, `other`. Use `null` for unavailable facts; never estimate a closing date or bid security.

### 2.3 Public notice example (fictional)

```json
{
  "uid": "XX-2099-9999-NOTC-001",
  "record_type": "public_notice",
  "title": "Statutory declaration affecting land in Sample District",
  "issue_id": "XX-2099-9999",
  "location": "Sample District",
  "keywords": ["land"],
  "notice": {"category": "land"},
  "source": {
    "pdf_page": 2,
    "printed_page": 2,
    "excerpt": "Notice is given that the land described in Schedule A in Sample District is subject to a statutory declaration."
  }
}
```

Notice categories: `land`, `insolvency`, `estate`, `court`, `licensing`, `professional`, `other`.

### 2.4 Regulation example (fictional)

```json
{
  "uid": "XX-2099-9999-REGL-001",
  "record_type": "regulation",
  "title": "The Example Regulation No. 1 of 2099",
  "issue_id": "XX-2099-9999",
  "organisation_ids": ["org:xx:example-authority"],
  "regulation": {
    "instrument_type": "regulation",
    "instrument_number": "1 of 2099",
    "effective_date": "2099-02-01"
  },
  "source": {
    "pdf_page": 2,
    "printed_page": 2,
    "excerpt": "The Example Regulation No. 1 of 2099 comes into effect on 1 February 2099."
  }
}
```

Instrument types: `act`, `regulation`, `order`, `rule`, `notification`, `by_law`, `other`.

## 3. People and identity verification

### 3.1 Person entity (fictional)

```json
{"person_id": "person:xx:a-example-001", "country_code": "XX", "canonical_name": "A. Example", "identity_status": "operator_verified", "verified_at": "2099-01-01", "basis": "Reviewed against the cited appointment notice."}
```

Rules:

- `person_id` format: `person:<lowercase-country>:<slug>`.
- Only `operator_verified` people receive public pages, sitemap entries and record links.
- `unverified` people remain in the file for review but are not published.
- Never combine two people because their names match. Create separate `person_id` values and, if a reviewer confirms they are the same person, update the record references explicitly.
- `basis` is an internal/public explanation of the review. Do not add private data or the operator's identity.

### 3.2 Name variants (fictional)

```json
{"variant_id": "VAR-XX-001", "person_id": "person:xx:a-example-001", "name": "A. E. Example", "verification": "operator_verified", "basis": "Reviewer matched the initialised form in the cited notice.", "reviewed_at": "2099-01-01", "source_record_uids": ["XX-2099-9999-APPT-001"]}
```

Only `operator_verified` variants appear in HTML, structured data and search. `unverified` variants are held. A variant is a name form, never a separate identity.

### 3.3 Same-name disambiguation

Two verified people may share a published name. They receive separate URLs and pages. Each page renders a "Same published name, different identity" notice linking the other. No records move between them automatically.

Run:

```bash
python scripts/report_name_candidates.py
```

The report is written to `reports/name-candidates.ndjson` (ignored by Git). It is advisory only and never edits data.

### 3.4 Operator-supplied identity mappings

Private verification evidence stays outside tracked data:

1. The operator records candidate mappings and the evidence location in a local file under `reports/` or outside the repository. `reports/` is ignored by Git.
2. The reviewer confirms or rejects each mapping and supplies the public `basis` wording.
3. Only the approved `person_id`, name variant, `verification`, `reviewed_at`, `basis` and public record UIDs are written to `entities/people.ndjson` or `entities/name-variants.ndjson`.
4. Never commit private documents, identity numbers, contact details, reviewer names or the operator's identity. `basis` must contain only the public-source justification.

An unconfirmed mapping remains unpublished. A name match alone is never sufficient.

## 4. Organisations

```json
{"organisation_id": "org:xx:example-authority", "country_code": "XX", "name": "Example Authority", "type": "statutory_body", "aliases": [], "identity_status": "operator_verified", "verified_at": "2099-01-01", "basis": "Reviewed against the cited notice."}
```

Types: `government_body`, `company`, `professional_body`, `statutory_body`, `other`. Organisation pages are generated for all curated organisations; unverified organisation pages are `noindex` and excluded from the sitemap. Do not infer ownership, government affiliation or current status beyond the cited notice.

## 5. Adding a country

1. Create `data/<cc>/country.json` with the ISO alpha-2 code, name, languages and Gazette title.
2. Add the code to `countries` in `config/site.json`.
3. Add extraction output under `data/<cc>/<year>/`, plus source, entity and record files.
4. Build. Existing records and URLs do not change.

## 6. Schemas

Regenerate JSON Schema from the Python models:

```bash
npm run schemas
```

Files are written to `schemas/` and checked into the repository. The build uses the Python models directly, so schema and validation cannot drift silently.

## 7. Official PDF URLs

`/extract_pdf.py --source-url <verified-url>` stores the URL in `issue.json`; `npm run sources` preserves it. The build appends `#page=<physical-page>` for page links. Never guess or construct a URL from a filename. If no verified URL exists, the site says so.


## 8. International source registry

`config/sources-intl.json` is the reusable registry of official publishers. Each entry records:

- country code, organisation, publication type and title;
- official URL, supported formats, languages and access method;
- reuse restrictions;
- access status: `verified`, `restricted`, `unavailable` or `planned`;
- optional adapter name, ingested record count, last-checked date and notes.

The build copies these rows into `/sources/`, so a source that is restricted or unavailable is disclosed rather than omitted. When adding an adapter, set `adapter` to the function name registered in `src/ingest/adapters.py`, ingest records, then run `npm run ingest -- --sync-registry` to refresh counts.

Adapters must not ingest:

- personal notices, deceased-estate notices, bankruptcy notices or similar personal records;
- contact-person names, e-mail addresses, telephone numbers or private addresses;
- bidder personal data.

Facts that are not present in the official source stay `null`. Do not infer a closing date, award value, reference number or organisation identity.
