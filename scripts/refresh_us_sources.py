"""Refresh US Federal Register and Grants.gov snapshots from official APIs.

Phase 1D audit found that the existing snapshots were either shared search
responses or anti-bot block pages.  This script re-fetches each cited document
from the publisher's documented API, replaces the snapshot with the retrieved
official text, and preserves the existing record/document identifiers.

    python scripts/refresh_us_sources.py

Requires network access.  No credentials are used.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
US = ROOT / "data" / "us"
UA = "GazetteRegistry/1.0 (+https://gazetteregistry.com; records research)"
RETRIEVED = date.today()
TODAY = date.today()


def fetch(url: str, *, data: bytes | None = None, content_type: str | None = None) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if content_type:
        headers["Content-Type"] = content_type
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read()
            time.sleep(0.6)
            return body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last_error}")


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_from_html(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", "\n", raw)
    return normalise(html.unescape(raw))


def read_ndjson(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    rows = sorted(rows, key=lambda row: row[key])
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def category_for(title: str) -> str:
    lowered = title.casefold()
    if "court" in lowered:
        return "court"
    if any(word in lowered for word in ("construction", "building", "facility")):
        return "construction"
    if any(word in lowered for word in ("infrastructure", "transport", "highway", "bridge", "port")):
        return "infrastructure"
    if any(word in lowered for word in ("technology", "cyber", "software", "data")):
        return "technology"
    return "general"


def refresh_federal_register(records: list[dict], documents: dict[str, dict]) -> int:
    updated = 0
    for record in records:
        if record["record_type"] != "public_notice":
            continue
        document = documents.get(record["source"].get("document_id", ""))
        if not document or document["source_id"] != "us-federal-register":
            continue
        match = re.search(r"/documents/\d{4}/\d{2}/\d{2}/([^/]+)/", str(record["source"]["official_url"]))
        if not match:
            print(f"skip {record['uid']}: cannot read document number")
            continue
        document_number = match.group(1)
        meta = json.loads(
            fetch(f"https://www.federalregister.gov/api/v1/documents/{document_number}.json")
        )
        raw_text_url = meta.get("raw_text_url")
        if not raw_text_url:
            print(f"skip {record['uid']}: no raw text URL")
            continue
        raw_bytes = fetch(raw_text_url)
        body = text_from_html(raw_bytes.decode("utf-8", "replace"))
        title = meta.get("title") or record["title"]
        text = normalise(title + " " + body)
        source_sha = hashlib.sha256(raw_bytes).hexdigest()
        publishers = [agency.get("name", "") for agency in meta.get("agencies", [])]
        publisher = "; ".join(name for name in publishers if name) or document.get("publisher")

        document.update(
            {
                "official_url": meta.get("html_url") or document["official_url"],
                "retrieved_at": RETRIEVED.isoformat(),
                "content_type": "text/html",
                "language": "en",
                "title": title,
                "publisher": publisher,
                "publication_date": meta.get("publication_date") or document.get("publication_date"),
                "source_sha256": source_sha,
                "source_bytes": len(raw_bytes),
                "checksum_scope": "source_response",
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text": text,
            }
        )
        record.update(
            {
                "title": title,
                "summary": meta.get("abstract") or record.get("summary"),
                "publication_date": meta.get("publication_date") or record["publication_date"],
                "language": "en",
                "keywords": sorted({"federal register", *record.get("keywords", [])}),
                "notice": {"category": category_for(title)},
            }
        )
        record["source"].update(
            {
                "kind": "html",
                "official_url": document["official_url"],
                "sha256": source_sha,
                "checksum_scope": "source_response",
                "retrieved_at": RETRIEVED.isoformat(),
                "excerpt": text[:360],
            }
        )
        updated += 1
        print(f"refreshed {record['uid']}: {title[:70]}")
    return updated


def grant_dates(entity: dict) -> tuple[str | None, str | None]:
    forecast = entity.get("forecast") or {}
    synopsis = entity.get("synopsis") or {}
    posting = (
        forecast.get("postingDateStr")
        or synopsis.get("postingDateStr")
        or forecast.get("postingDate")
        or synopsis.get("postingDate")
    )
    closing = (
        forecast.get("estApplicationResponseDateStr")
        or synopsis.get("responseDateStr")
        or forecast.get("estApplicationResponseDate")
        or synopsis.get("responseDate")
    )

    def iso(value: str | None) -> str | None:
        if not value:
            return None
        if re.match(r"^\d{4}-\d{2}-\d{2}", value):
            return value[:10]
        for fmt in ("%b %d, %Y %I:%M:%S %p %Z", "%b %d, %Y"):
            try:
                from datetime import datetime

                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None

    return iso(posting), iso(closing)


def refresh_grants(records: list[dict], documents: dict[str, dict]) -> int:
    updated = 0
    for record in records:
        tender = record.get("tender")
        document = documents.get(record["source"].get("document_id", ""))
        if not tender or not document or document["source_id"] != "us-grants-gov":
            continue
        match = re.search(r"/search-results-detail/(\d+)", str(record["source"]["official_url"]))
        if not match:
            print(f"skip {record['uid']}: cannot read opportunity id")
            continue
        payload = json.dumps({"opportunityId": int(match.group(1))}).encode("utf-8")
        raw_bytes = fetch(
            "https://api.grants.gov/v1/api/fetchOpportunity",
            data=payload,
            content_type="application/json",
        )
        entity = json.loads(raw_bytes)["data"]
        title = entity.get("opportunityTitle") or record["title"]
        agency = (
            (entity.get("agencyDetails") or {}).get("agencyName")
            or (entity.get("topAgencyDetails") or {}).get("agencyName")
            or "Grants.gov"
        )
        source_status = entity.get("ost") or entity.get("docType") or "unknown"
        posting, closing = grant_dates(entity)
        description = (
            (entity.get("forecast") or {}).get("forecastDesc")
            or (entity.get("synopsis") or {}).get("synopsisDesc")
            or ""
        )
        text = normalise(
            "\n".join(
                part
                for part in (
                    f"Opportunity number: {entity.get('opportunityNumber')}",
                    f"Title: {title}",
                    f"Agency: {agency}",
                    f"Status: {source_status}",
                    f"Posting date: {posting or 'not stated'}",
                    f"Application response date: {closing or 'not stated'}",
                    f"Description: {description}",
                )
                if part
            )
        )
        source_sha = hashlib.sha256(raw_bytes).hexdigest()

        # A forecast is not an open application opportunity, even when its
        # estimated response date is in the future.
        if str(source_status).casefold() == "forecasted":
            status = "unknown"
        elif closing and closing < TODAY.isoformat():
            status = "closed"
        elif closing:
            status = "open"
        else:
            status = "unknown"

        document.update(
            {
                "retrieved_at": RETRIEVED.isoformat(),
                "content_type": "application/json",
                "language": "en",
                "title": title,
                "publisher": agency,
                "publication_date": posting or document.get("publication_date"),
                "source_sha256": source_sha,
                "source_bytes": len(raw_bytes),
                "checksum_scope": "source_response",
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text": text,
            }
        )
        record.update(
            {
                "title": title,
                "publication_date": posting or record["publication_date"],
                "language": "en",
                "keywords": sorted({"grant", "grants.gov", *record.get("keywords", [])}),
                "summary": description[:700] or record.get("summary"),
            }
        )
        tender.update(
            {
                "opportunity_kind": "grant",
                "reference": entity.get("opportunityNumber") or tender["reference"],
                "sector": "other",
                "status": status,
                "source_status": str(source_status).title(),
                "status_as_of": RETRIEVED.isoformat(),
                "closing_date": closing,
                "closing_time": None,
                "currency": "USD",
                "issuer_organisation_id": None,
            }
        )
        record["source"].update(
            {
                "kind": "json",
                "sha256": source_sha,
                "checksum_scope": "source_response",
                "retrieved_at": RETRIEVED.isoformat(),
                "excerpt": text[:360],
            }
        )
        updated += 1
        print(f"refreshed {record['uid']}: {title[:70]} ({source_status})")
    return updated


def main() -> int:
    records_path = US / "records" / "records.ndjson"
    documents_path = US / "sources" / "documents.ndjson"
    records = read_ndjson(records_path)
    documents = {document["document_id"]: document for document in read_ndjson(documents_path)}
    federal = refresh_federal_register(records, documents)
    grants = refresh_grants(records, documents)
    write_ndjson(records_path, records, "uid")
    write_ndjson(documents_path, list(documents.values()), "document_id")
    print(f"updated {federal} Federal Register and {grants} Grants.gov records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
