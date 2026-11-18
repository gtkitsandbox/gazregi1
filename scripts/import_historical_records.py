"""Curate verified historical records from an extracted Gazette issue.

Run after extracting a historical PDF with ``scripts/extract_pdf.py``.  The
script only writes records whose verbatim excerpt is present in the extracted
page text.  It does not download, OCR or guess missing metadata.

    python scripts/import_historical_records.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ISSUES = {
    "GB-1914-29002": {
        "dir": DATA / "gb" / "1914" / "1914-12-08-29002",
        "pdf": ROOT / "raw" / "Gazette-1914-12-08-S.pdf",
    },
    "GB-1915-29131": {
        "dir": DATA / "gb" / "1915" / "1915-04-13-29131",
        "pdf": ROOT / "raw" / "Gazette-1915-04-13-S.pdf",
    },
}
RETRIEVED = "2026-11-18"

RECORDS = [
    {
        "uid": "GB-1915-29131-APPT-001",
        "issue_id": "GB-1915-29131",
        "record_type": "promotion",
        "title": "Havelock Hudson promoted to Major-General",
        "page": 1,
        "excerpt": (
            "His Majesty the KING has been graciously pleased to approve of the "
            "promotion to the- rank of Major-General of Colonel (temporary "
            "Brigadier-General) Havelock Hudson, C.B., C.I.E., for distinguished "
            "service in the field, with effect from the 18th February, 1915, inclusive"
        ),
        "person": {
            "person_id": "person:gb:havelock-hudson",
            "canonical_name": "Havelock Hudson",
            "published_name": "Havelock Hudson",
            "position": "Major-General, Indian Army (promoted from Colonel, temporary Brigadier-General)",
            "position_kind": "promotion",
            "variant": "Havelock Hudson, C.B., C.I.E.",
        },
        "organisation": {
            "organisation_id": "org:gb:indian-army",
            "name": "Indian Army",
            "type": "government_body",
        },
        "issuing_organisation_name": "War Office",
        "keywords": ["promotion", "military", "Indian Army"],
    },
    {
        "uid": "GB-1914-29002-APPT-001",
        "issue_id": "GB-1914-29002",
        "record_type": "appointment",
        "title": "Havelock Hudson appointed to the General Staff",
        "page": 1,
        "excerpt": (
            "Colonel (temporary Brigadier-General) Havelock Hudson, C.B., C.I.E., "
            "and to retain his temporary rank."
        ),
        "person": {
            "person_id": "person:gb:havelock-hudson",
            "canonical_name": "Havelock Hudson",
            "published_name": "Havelock Hudson",
            "position": "Colonel (temporary Brigadier-General), General Staff",
            "position_kind": "appointment",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:gb:indian-army",
            "name": "Indian Army",
            "type": "government_body",
        },
        "issuing_organisation_name": "War Office",
        "keywords": ["appointment", "military", "General Staff"],
    },
    {
        "uid": "GB-1915-29131-APPT-002",
        "issue_id": "GB-1915-29131",
        "record_type": "appointment",
        "title": "Captain Ian M. Smith seconded to a special appointment",
        "page": 3,
        "excerpt": (
            "Captain Ian M. Smith, Prince Albert's (Somerset Light Infantry),/ "
            "and to be seconded.. Dated 24th February, 1915."
        ),
        "person": {
            "person_id": "person:gb:ian-m-smith",
            "canonical_name": "Ian M. Smith",
            "published_name": "Ian M. Smith",
            "position": "Captain, Prince Albert's (Somerset Light Infantry); seconded",
            "position_kind": "appointment",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:gb:somerset-light-infantry",
            "name": "Prince Albert's (Somerset Light Infantry)",
            "type": "government_body",
        },
        "issuing_organisation_name": "War Office",
        "keywords": ["appointment", "military"],
    },
]


def read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: row[key])
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main() -> int:
    issue_data = {
        issue_id: json.loads((paths["dir"] / "issue.json").read_text(encoding="utf-8"))
        for issue_id, paths in ISSUES.items()
    }
    texts_by_issue = {
        issue_id: {
            json.loads(line)["uid"]: json.loads(line)["text"]
            for line in gzip.open(paths["dir"] / "text.jsonl.gz", "rt", encoding="utf-8")
        }
        for issue_id, paths in ISSUES.items()
    }
    pdf_shas = {
        issue_id: hashlib.sha256(paths["pdf"].read_bytes()).hexdigest()
        for issue_id, paths in ISSUES.items()
    }

    base = DATA / "gb"
    records = read_ndjson(base / "records" / "records.ndjson")
    people = read_ndjson(base / "entities" / "people.ndjson")
    organisations = read_ndjson(base / "entities" / "organisations.ndjson")
    variants = read_ndjson(base / "entities" / "name-variants.ndjson")
    registry = read_ndjson(base / "sources" / "registry.ndjson")
    previous_issue_records = len(
        [row for row in records if row.get("issue_id") in ISSUES]
    )

    for item in RECORDS:
        issue_id = item["issue_id"]
        issue = issue_data[issue_id]
        texts = texts_by_issue[issue_id]
        page_uid = f"{issue_id}-PAGE-{item['page']:03d}"
        if normalise(item["excerpt"]) not in normalise(texts[page_uid]):
            raise SystemExit(f"{item['uid']}: excerpt not found on {page_uid}")
        person = item["person"]
        organisation = item["organisation"]
        record = {
            "uid": item["uid"],
            "record_type": item["record_type"],
            "title": item["title"],
            "summary": None,
            "issue_id": issue_id,
            "publication_date": issue["publication_date"],
            "language": "en",
            "issuing_organisation_name": item["issuing_organisation_name"],
            "people": [
                {
                    "person_id": person["person_id"],
                    "published_name": person["published_name"],
                    "position": person["position"],
                    "position_kind": person["position_kind"],
                    "organisation_ids": [organisation["organisation_id"]],
                }
            ],
            "organisation_ids": [organisation["organisation_id"]],
            "location": "United Kingdom",
            "keywords": item["keywords"],
            "tender": None,
            "regulation": None,
            "notice": None,
            "source": {
                "kind": "pdf",
                "pdf_page": item["page"],
                "printed_page": None,
                "document_id": None,
                "excerpt": item["excerpt"],
                "official_url": issue["source_url"],
                "sha256": pdf_shas[issue_id],
                "checksum_scope": "original_source",
                "retrieved_at": RETRIEVED,
            },
        }
        records = [row for row in records if row["uid"] != item["uid"]] + [record]

        people = [row for row in people if row["person_id"] != person["person_id"]]
        people.append(
            {
                "person_id": person["person_id"],
                "country_code": "GB",
                "canonical_name": person["canonical_name"],
                "identity_status": "operator_verified",
                "verified_at": RETRIEVED,
                "basis": (
                    f"Identity reviewed against the official Gazette {issue_id}, "
                    f"page {item['page']}, published {issue['publication_date']} and "
                    f"retrieved {RETRIEVED}."
                ),
            }
        )
        organisations = [
            row
            for row in organisations
            if row["organisation_id"] != organisation["organisation_id"]
        ]
        organisations.append(
            {
                "organisation_id": organisation["organisation_id"],
                "country_code": "GB",
                "name": organisation["name"],
                "type": organisation["type"],
                "aliases": [],
                "identity_status": "operator_verified",
                "verified_at": RETRIEVED,
                "basis": (
                    f"Named in the official Gazette {issue_id}, page {item['page']}, "
                    f"published {issue['publication_date']}."
                ),
            }
        )
        if person["variant"]:
            variant_id = f"VAR-GB-{item['uid'].rsplit('-', 1)[-1]}"
            variants = [row for row in variants if row["variant_id"] != variant_id]
            variants.append(
                {
                    "variant_id": variant_id,
                    "person_id": person["person_id"],
                    "name": person["variant"],
                    "verification": "operator_verified",
                    "basis": (
                        f"Name form printed in the cited Gazette notice {item['uid']}."
                    ),
                    "reviewed_at": RETRIEVED,
                    "source_record_uids": [item["uid"]],
                }
            )

    gazette_rows = [row for row in registry if row["source_id"] == "gb-the-gazette"]
    if gazette_rows:
        current_issue_records = len(
            [row for row in records if row.get("issue_id") in ISSUES]
        )
        gazette_rows[0]["records_ingested"] = (
            int(gazette_rows[0].get("records_ingested") or 0)
            - previous_issue_records
            + current_issue_records
        )
        gazette_rows[0]["last_checked"] = RETRIEVED
        gazette_rows[0]["notes"] = (
            "Historical London Gazette issues are curated from official PDFs; "
            "page-level provenance is retained and OCR is not used."
        )
    registry = [row for row in registry if row["source_id"] != "gb-the-gazette"] + gazette_rows

    write_ndjson(base / "records" / "records.ndjson", records, "uid")
    write_ndjson(base / "entities" / "people.ndjson", people, "person_id")
    write_ndjson(base / "entities" / "organisations.ndjson", organisations, "organisation_id")
    write_ndjson(base / "entities" / "name-variants.ndjson", variants, "variant_id")
    write_ndjson(base / "sources" / "registry.ndjson", registry, "source_id")
    print(f"imported {len(RECORDS)} historical records from {len(ISSUES)} Gazette issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
