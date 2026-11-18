"""Create verified Sri Lankan gazette notice records from the tracked PDFs.

The four gazettes supplied in Phase 1C are the source basis.  Each record cites
one page, one printed page number and the SHA-256 of the original PDF.  The
official source URL remains null because no authoritative URL has been
resolved; nothing is fabricated.

    python scripts/import_lk_notices.py
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LK = ROOT / "data" / "lk"
TODAY = date.today()

NOTICES = [
    {
        "uid": "LK-2026-2502-NOTC-001",
        "issue": "LK-2026-2502",
        "page": "LK-2026-2502-PAGE-004",
        "title": "Open Recruitment to the Post of Legal Officer (Executive Officer Service Category Grade III), Ministry of Foreign Affairs, Foreign Employment and Tourism",
        "category": "professional",
        "organisation": {
            "organisation_id": "org:lk:public-service-commission",
            "name": "Public Service Commission",
        },
    },
    {
        "uid": "LK-2026-2504-NOTC-001",
        "issue": "LK-2026-2504",
        "page": "LK-2026-2504-PAGE-004",
        "title": "Post of Registrar of Births, Deaths and Marriages/ Additional Marriages (Kandyan/ General), Badulla District",
        "category": "professional",
        "organisation": {
            "organisation_id": "org:lk:registrar-generals-department",
            "name": "Registrar General's Department",
        },
    },
    {
        "uid": "LK-2026-2505-NOTC-001",
        "issue": "LK-2026-2505",
        "page": "LK-2026-2505-PAGE-004",
        "title": "Filling of Vacancies for the Post of Field Assistant (Supervisory) in the Primary - Non-Technical Service Category - 2026",
        "category": "professional",
        "organisation": {
            "organisation_id": "org:lk:ministry-of-environment",
            "name": "Ministry of Environment",
        },
    },
    {
        "uid": "LK-2026-2506-NOTC-001",
        "issue": "LK-2026-2506",
        "page": "LK-2026-2506-PAGE-004",
        "title": "Vacancies at the Merchant Shipping Secretariat: Port State Controller (Engineering), Examiner (Engineering) and Legal Officer",
        "category": "professional",
        "organisation": {
            "organisation_id": "org:lk:merchant-shipping-secretariat",
            "name": "Merchant Shipping Secretariat",
        },
    },
]


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    rows = sorted(rows, key=lambda row: row[key])
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def issue_dir(issue_id: str) -> Path:
    matches = list((LK / "2026").glob(f"*{issue_id.rsplit('-', 1)[-1]}"))
    if len(matches) != 1:
        raise RuntimeError(f"cannot resolve issue directory for {issue_id}: {matches}")
    return matches[0]


def main() -> int:
    sources = {row["issue_id"]: row for row in read_ndjson(LK / "sources" / "sources.ndjson")}
    records = [row for row in read_ndjson(LK / "records" / "records.ndjson") if row["record_type"] != "public_notice"]
    organisations = read_ndjson(LK / "entities" / "organisations.ndjson")

    for notice in NOTICES:
        directory = issue_dir(notice["issue"])
        issue = json.loads((directory / "issue.json").read_text(encoding="utf-8"))
        pages = {row["uid"]: row for row in read_ndjson(directory / "pages.ndjson")}
        page = pages[notice["page"]]
        text = ""
        with gzip.open(directory / "text.jsonl.gz", "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["uid"] == notice["page"]:
                    text = row["text"]
                    break
        if not text:
            raise RuntimeError(f"no text for {notice['page']}")
        start = text.find("Post - Vacant")
        if start == -1:
            start = 0
        excerpt = normalise(text[start : start + 320])
        if len(excerpt) < 20:
            raise RuntimeError(f"excerpt too short for {notice['page']}")
        source = sources[notice["issue"]]
        record = {
            "uid": notice["uid"],
            "record_type": "public_notice",
            "title": notice["title"],
            "summary": None,
            "issue_id": notice["issue"],
            "publication_date": issue["publication_date"],
            "language": "en",
            "issuing_organisation_name": notice["organisation"]["name"],
            "people": [],
            "organisation_ids": [notice["organisation"]["organisation_id"]],
            "location": None,
            "keywords": ["gazette", "vacancy", "public service"],
            "tender": None,
            "regulation": None,
            "notice": {"category": notice["category"]},
            "source": {
                "kind": "pdf",
                "pdf_page": page["physical_pdf_page"],
                "printed_page": page["printed_page"],
                "document_id": None,
                "excerpt": excerpt,
                "official_url": issue["source_url"],
                "sha256": source["sha256"],
                "checksum_scope": "original_source",
                "retrieved_at": None,
            },
        }
        records = [row for row in records if row["uid"] != notice["uid"]]
        records.append(record)
        organisation = {
            "organisation_id": notice["organisation"]["organisation_id"],
            "country_code": "LK",
            "name": notice["organisation"]["name"],
            "type": "government_body",
            "aliases": [],
            "identity_status": "operator_verified",
            "verified_at": TODAY.isoformat(),
            "basis": f"Named in the tracked gazette {issue['gazette_no']} ({issue['publication_date']}), "
            f"page {page['printed_page'] or page['physical_pdf_page']}.",
        }
        organisations = [
            row
            for row in organisations
            if row["organisation_id"] != organisation["organisation_id"]
        ]
        organisations.append(organisation)
        print(f"{notice['uid']}: {notice['title'][:70]}")

    write_ndjson(LK / "records" / "records.ndjson", records, "uid")
    write_ndjson(LK / "entities" / "organisations.ndjson", organisations, "organisation_id")

    country_path = LK / "country.json"
    country = json.loads(country_path.read_text(encoding="utf-8"))
    country["coverage_status"] = "partial"
    country_path.write_text(json.dumps(country, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(records)} LK records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
