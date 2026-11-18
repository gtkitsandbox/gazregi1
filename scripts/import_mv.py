"""Import the Maldives Phase 1D sample from official sites.

Sources (both verified reachable during Phase 1D):

* https://www.gazette.gov.mv/iulaan  — public notices, Dhivehi
* https://www.finance.gov.mv/tenders — national tender notices, English

The script fetches the cited detail page, stores a normalised text snapshot of
that response, and records the HTTP response checksum (``source_response``,
not a checksum of the linked PDF).  Titles, references and dates are copied
verbatim from the official page; nothing is translated into the factual
fields.

    python scripts/import_mv.py
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "mv"
UA = "GazetteRegistry/1.0 (+https://gazetteregistry.com; records research)"
TODAY = date.today()

NOTICES = [
    ("422294", "construction"),
    ("422293", "construction"),
    ("422257", "infrastructure"),
    ("422256", "construction"),
    ("422152", "infrastructure"),
    ("422115", "construction"),
    ("422113", "construction"),
    ("422108", "construction"),
    ("422081", "construction"),
    ("422054", "technology"),
]

TENDERS = [
    "development-of-henveiru-urban-primary-healthcare-center",
    "construction-of-mnu-l-gan-campus-and-dhanaal",
    "construction-of-sh-feydhoo-mosque-3099",
    "construction-of-12-classroom-at-ga-atoll-education-centre",
    "design-and-construction-works-of-an-ash-landfill-cell-and-associated-infrastructure-for-the-waste-to-energy-plant-at-south-regional-waste-management-facility-in-hithadhoo-addu-city",
    "development-of-gdh-madaveli-football-ground-3017",
    "construction-of-mnu-staff-and-student-accommodation-block-in-aathoddoo",
    "procurement-of-sdwan-equipment-and-services-to-improve-the-government-network-infra-and-connect-200-locations-retender",
    "design-build-of-mnu-campus-in-dh-kudahuvadhoo",
    "design-build-of-mnu-campus-in-mmuli",
]

DHIVEHI_MONTHS = {
    "ޖަނަވަރީ": 1,
    "ފެބްރުއަރީ": 2,
    "މާރިޗު": 3,
    "އޭޕްރީލް": 4,
    "މޭ": 5,
    "ޖޫން": 6,
    "ޖުލައި": 7,
    "އޯގަސްޓު": 8,
    "ސެޕްޓެމްބަރު": 9,
    "އޮކްޓޯބަރު": 10,
    "ނޮވެންބަރު": 11,
    "ޑިސެމްބަރު": 12,
}
ENGLISH_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
    )
    if name
}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read()
            time.sleep(0.8)
            return body
        except OSError as exc:  # URLError is an OSError
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return normalise(html.unescape(raw))


def block(raw: str, start: str, end: str) -> str:
    match = re.search(start + r"(.*?)" + end, raw, re.S)
    return match.group(1) if match else ""


def dhivehi_date(value: str) -> str | None:
    match = re.search(r"(\d{1,2})\s+([^\s]+)\s+(\d{4})", value)
    if not match or match.group(2) not in DHIVEHI_MONTHS:
        return None
    day, month, year = match.groups()
    return f"{int(year):04d}-{DHIVEHI_MONTHS[month]:02d}-{int(day):02d}"


def english_date(value: str) -> str | None:
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value)
    if not match or match.group(2) not in ENGLISH_MONTHS:
        return None
    day, month, year = match.groups()
    return f"{int(year):04d}-{ENGLISH_MONTHS[month]:02d}-{int(day):02d}"


def slugify(value: str) -> str:
    value = html.unescape(value).casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:60] or "office"


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: row[key])
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def import_notice(identifier: str, category: str, index: int) -> tuple[dict, dict, dict]:
    url = f"https://www.gazette.gov.mv/iulaan/{identifier}"
    raw_bytes = fetch(url)
    raw = raw_bytes.decode("utf-8", "replace")
    title = strip_tags(block(raw, r'<div class="iulaan iulaan-title center">', r"</div>"))
    office = strip_tags(block(raw, r'<span class="office-name">', r"</span>"))
    body_parts = [
        strip_tags(part)
        for part in re.findall(r'<div class="col-md-12 details">(.*?)</div>\s*(?=<div class="col-md-12)', raw, re.S)
    ]
    body = normalise(" ".join(part for part in body_parts if part))
    reference = strip_tags(block(raw, r"ނަންބަރު:\s*<span class=\"en\"[^>]*>", r"</span>"))
    published_raw = strip_tags(block(raw, r"ޕަބްލިޝްކުރި ތާރީޚު:", r"</div>"))
    deadline_raw = strip_tags(block(raw, r"ސުންގަޑި:", r"</div>"))
    published = dhivehi_date(published_raw)
    deadline = dhivehi_date(deadline_raw)
    if not published:
        raise RuntimeError(f"{identifier}: could not parse publication date from {published_raw!r}")

    text = normalise(
        f"{title} | {office} | {body} | ނަންބަރު: {reference} | ޕަބްލިޝްކުރި ތާރީޚު: {published_raw} | ސުންގަޑި: {deadline_raw}"
    )
    excerpt = text[:360]
    sentence_end = text.rfind("ެވެ.", 0, 360)
    if sentence_end != -1:
        excerpt = text[: sentence_end + 5]
    document = {
        "document_id": f"DOC-MV-{index:04d}",
        "country_code": "MV",
        "source_id": "mv-gazette",
        "official_url": url,
        "retrieved_at": TODAY.isoformat(),
        "content_type": "text/html",
        "language": "dv",
        "title": title,
        "publisher": "Government of the Maldives",
        "publication_date": published,
        "source_bytes": len(raw_bytes),
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "checksum_scope": "source_response",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    org_id = f"org:mv:issuer-{identifier}"
    record = {
        "uid": f"MV-{published[:4]}-NOTC-{index:03d}",
        "record_type": "public_notice",
        "title": title,
        "summary": None,
        "issue_id": None,
        "publication_date": published,
        "language": "dv",
        "issuing_organisation_name": office,
        "people": [],
        "organisation_ids": [org_id],
        "location": None,
        "keywords": ["iulaan", "public notice", category, "Dhivehi"],
        "tender": None,
        "regulation": None,
        "notice": {"category": category},
        "source": {
            "kind": "html",
            "pdf_page": None,
            "printed_page": None,
            "document_id": document["document_id"],
            "excerpt": excerpt,
            "official_url": url,
            "sha256": document["source_sha256"],
            "checksum_scope": "source_response",
            "retrieved_at": TODAY.isoformat(),
        },
    }
    organisation = {
        "organisation_id": org_id,
        "country_code": "MV",
        "name": office,
        "type": "government_body",
        "aliases": [],
        "identity_status": "operator_verified",
        "verified_at": TODAY.isoformat(),
        "basis": f"Named as the issuing office on official notice {url} retrieved {TODAY.isoformat()}.",
    }
    # The deadline is retained in the snapshot text but not modelled as a
    # tender closing date, because the notice is published as a public notice.
    print(f"notice {record['uid']}: {title[:60]} ({published}, deadline {deadline or 'not stated'})")
    return record, document, organisation


def map_sector(project_type: str, project_sector: str) -> str:
    lowered = f"{project_type} {project_sector}".casefold()
    if "works" in lowered or "construction" in lowered:
        return "civil_works"
    if "goods" in lowered or "supply" in lowered:
        return "goods"
    if "service" in lowered:
        return "services"
    if "information technology" in lowered or "ict" in lowered:
        return "it"
    return "other"


def import_tender(slug: str, index: int) -> tuple[dict, dict]:
    url = f"https://www.finance.gov.mv/tenders/{slug}"
    raw_bytes = fetch(url)
    raw = raw_bytes.decode("utf-8", "replace")
    title = strip_tags(block(raw, r'<div class="text-2xl font-bold lg:text-3xl text-mof-blue-400">', r"<span"))
    updated_raw = strip_tags(block(raw, r"</svg>\s*<span class=\"text-sm font-medium \">", r"</span>"))
    fields = {}
    for label in ("Ref", "Procurement Approach", "Deadline", "Project Type", "Project Sector"):
        value = strip_tags(
            block(
                raw,
                rf'>{label}:</div>\s*<div class="col-span-1 sm:col-span-3 lg:col-span-1">',
                r"</div>",
            )
        )
        fields[label] = value
    deadline_match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}:\d{2})", fields["Deadline"])
    if not deadline_match:
        raise RuntimeError(f"{slug}: cannot parse deadline {fields['Deadline']!r}")
    day, month, year, clock = deadline_match.groups()
    closing = f"{year}-{month}-{day}"
    published = english_date(updated_raw)
    if not published:
        raise RuntimeError(f"{slug}: cannot parse date {updated_raw!r}")
    status = "closed" if closing < TODAY.isoformat() else "open"

    text = normalise(
        f"Title: {title} | Ref: {fields['Ref']} | Procurement approach: {fields['Procurement Approach']} "
        f"| Deadline: {fields['Deadline']} | Project type: {fields['Project Type']} "
        f"| Project sector: {fields['Project Sector']} | Updated: {updated_raw}"
    )
    document = {
        "document_id": f"DOC-MV-{100 + index:04d}",
        "country_code": "MV",
        "source_id": "mv-finance-tenders",
        "official_url": url,
        "retrieved_at": TODAY.isoformat(),
        "content_type": "text/html",
        "language": "en",
        "title": title,
        "publisher": "Ministry of Finance and Public Enterprises",
        "publication_date": published,
        "source_bytes": len(raw_bytes),
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "checksum_scope": "source_response",
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    record = {
        "uid": f"MV-{published[:4]}-TEND-{index:03d}",
        "record_type": "tender",
        "title": title,
        "summary": None,
        "issue_id": None,
        "publication_date": published,
        "language": "en",
        "issuing_organisation_name": "Ministry of Finance and Public Enterprises",
        "people": [],
        "organisation_ids": ["org:mv:ministry-of-finance-and-public-enterprises"],
        "location": "Maldives",
        "keywords": ["tender", fields["Project Type"].casefold(), fields["Project Sector"].casefold()],
        "tender": {
            "reference": fields["Ref"],
            "issuer_organisation_id": "org:mv:ministry-of-finance-and-public-enterprises",
            "sector": map_sector(fields["Project Type"], fields["Project Sector"]),
            "opportunity_kind": "tender",
            "status": status,
            "source_status": "Published",
            "status_as_of": TODAY.isoformat(),
            "location": "Maldives",
            "closing_date": closing,
            "closing_time": clock,
            "document_deadline": None,
            "bid_security_lkr": None,
            "bid_security": None,
            "currency": "MVR",
            "awarded_to": None,
            "award_amount": None,
            "award_date": None,
        },
        "regulation": None,
        "notice": None,
        "source": {
            "kind": "html",
            "pdf_page": None,
            "printed_page": None,
            "document_id": document["document_id"],
            "excerpt": text[:360],
            "official_url": url,
            "sha256": document["source_sha256"],
            "checksum_scope": "source_response",
            "retrieved_at": TODAY.isoformat(),
        },
    }
    print(f"tender {record['uid']}: {title[:60]} ({status}, closes {closing} {clock})")
    return record, document


def main() -> int:
    records: list[dict] = []
    documents: list[dict] = []
    organisations: dict[str, dict] = {}
    for index, (identifier, category) in enumerate(NOTICES, start=1):
        record, document, organisation = import_notice(identifier, category, index)
        records.append(record)
        documents.append(document)
        organisations[organisation["organisation_id"]] = organisation
    for index, slug in enumerate(TENDERS, start=1):
        record, document = import_tender(slug, index)
        records.append(record)
        documents.append(document)

    organisations["org:mv:ministry-of-finance-and-public-enterprises"] = {
        "organisation_id": "org:mv:ministry-of-finance-and-public-enterprises",
        "country_code": "MV",
        "name": "Ministry of Finance and Public Enterprises",
        "type": "government_body",
        "aliases": [],
        "identity_status": "operator_verified",
        "verified_at": TODAY.isoformat(),
        "basis": "Named as the publishing ministry on https://www.finance.gov.mv/tenders, retrieved "
        + TODAY.isoformat()
        + ".",
    }

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "country.json").write_text(
        json.dumps(
            {
                "country_code": "MV",
                "name": "Maldives",
                "region": "Asia",
                "languages": ["dv", "en"],
                "gazette_name": "Government Gazette of the Maldives",
                "publisher_name": "Government of the Maldives",
                "default_language": "dv",
                "coverage_status": "partial",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_ndjson(DATA / "records" / "records.ndjson", records, "uid")
    write_ndjson(DATA / "sources" / "documents.ndjson", documents, "document_id")
    write_ndjson(DATA / "entities" / "organisations.ndjson", list(organisations.values()), "organisation_id")
    write_ndjson(
        DATA / "sources" / "registry.ndjson",
        [
            {
                "source_id": "mv-gazette",
                "country_code": "MV",
                "organisation": "Government of the Maldives",
                "publication_type": "gazette",
                "title": "Government Gazette — Public Notices (Iulaan)",
                "official_url": "https://www.gazette.gov.mv/iulaan",
                "formats": ["html", "pdf"],
                "languages": ["dv"],
                "access_method": "Official public notice listing and detail pages",
                "reuse_restrictions": "Official government publication. Records here quote short excerpts with attribution and link to the official notice; the linked PDF attachments remain subject to the publisher's terms.",
                "access_status": "verified",
                "adapter": None,
                "records_ingested": len(NOTICES),
                "last_checked": TODAY.isoformat(),
                "notes": "Dhivehi content is retained verbatim. English keywords are editorial classification only.",
            },
            {
                "source_id": "mv-finance-tenders",
                "country_code": "MV",
                "organisation": "Ministry of Finance and Public Enterprises",
                "publication_type": "procurement",
                "title": "Recent Tenders",
                "official_url": "https://www.finance.gov.mv/tenders",
                "formats": ["html", "pdf"],
                "languages": ["en"],
                "access_method": "Official tender listing and detail pages",
                "reuse_restrictions": "Official government tender publication. Records here quote the published metadata with attribution and link to the official notice.",
                "access_status": "verified",
                "adapter": None,
                "records_ingested": len(TENDERS),
                "last_checked": TODAY.isoformat(),
                "notes": "Deadlines are as published; status is calculated from the deadline date.",
            },
        ],
        "source_id",
    )
    print(f"wrote {len(records)} records and {len(documents)} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
