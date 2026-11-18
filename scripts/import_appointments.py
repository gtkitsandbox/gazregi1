"""Import verified professional appointment records for Phase 1D.

Sources are official government press releases fetched over HTTP:

* Maldives — The President's Office (English releases)
* United Kingdom — GOV.UK news announcements

Each record links one published name to one verified person entity and one
organisation.  The excerpt is copied from the stored normalised snapshot, so
the same source cannot drift from the displayed evidence.

    python scripts/import_appointments.py
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
UA = "GazetteRegistry/1.0 (+https://gazetteregistry.com; records research)"
TODAY = date.today()

APPOINTMENTS = [
    {
        "country": "mv",
        "url": "https://presidency.gov.mv/Press/Article/37107",
        "source_id": "mv-presidency",
        "document_id": "DOC-MV-0201",
        "record_uid": "MV-2026-APPT-001",
        "title": "President appoints Ambassador to the Kingdom of Belgium and the European Union",
        "published": "2026-08-03",
        "publisher": "The President's Office, Maldives",
        "person": {
            "person_id": "person:mv:fathimath-dhiyana",
            "canonical_name": "Fathimath Dhiyana",
            "published_name": "Uza Fathimath Dhiyana",
            "position": "Ambassador of the Maldives to the Kingdom of Belgium and the European Union",
            "variant": "Uza Fathimath Dhiyana",
        },
        "organisation": {
            "organisation_id": "org:mv:government-of-the-maldives",
            "name": "Government of the Maldives",
            "type": "government_body",
        },
    },
    {
        "country": "mv",
        "url": "https://presidency.gov.mv/Press/Article/36870",
        "source_id": "mv-presidency",
        "document_id": "DOC-MV-0202",
        "record_uid": "MV-2026-APPT-002",
        "title": "President appoints ambassadors to UAE and Qatar",
        "published": "2026-06-25",
        "publisher": "The President's Office, Maldives",
        "person": {
            "person_id": "person:mv:thoriq-ibrahim",
            "canonical_name": "Thoriq Ibrahim",
            "published_name": "Thoriq Ibrahim",
            "position": "Ambassador to the United Arab Emirates",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:mv:government-of-the-maldives",
            "name": "Government of the Maldives",
            "type": "government_body",
        },
    },
    {
        "country": "mv",
        "url": "https://presidency.gov.mv/Press/Article/36870",
        "source_id": "mv-presidency",
        "document_id": "DOC-MV-0202",
        "record_uid": "MV-2026-APPT-003",
        "title": "President appoints ambassadors to UAE and Qatar",
        "published": "2026-06-25",
        "publisher": "The President's Office, Maldives",
        "person": {
            "person_id": "person:mv:adam-shareef-umar",
            "canonical_name": "Adam Shareef Umar",
            "published_name": "Adam Shareef Umar",
            "position": "Ambassador to the State of Qatar",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:mv:government-of-the-maldives",
            "name": "Government of the Maldives",
            "type": "government_body",
        },
    },
    {
        "country": "mv",
        "url": "https://presidency.gov.mv/Press/Article/36487",
        "source_id": "mv-presidency",
        "document_id": "DOC-MV-0203",
        "record_uid": "MV-2026-APPT-004",
        "title": "President appoints Mohamed Hussain Shareef as Chief Government Spokesperson",
        "published": "2026-04-15",
        "publisher": "The President's Office, Maldives",
        "person": {
            "person_id": "person:mv:mohamed-hussain-shareef",
            "canonical_name": "Mohamed Hussain Shareef",
            "published_name": "Mohamed Hussain Shareef",
            "position": "Chief Government Spokesperson at the President's Office, with ministerial rank",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:mv:the-presidents-office",
            "name": "The President's Office",
            "type": "government_body",
        },
    },
    {
        "country": "gb",
        "url": "https://www.gov.uk/government/news/gareth-davies-appointed-as-new-home-office-permanent-secretary",
        "source_id": "gb-govuk-news",
        "document_id": "DOC-GB-0054",
        "record_uid": "GB-2026-APPT-001",
        "title": "Gareth Davies Appointed as New Home Office Permanent Secretary",
        "published": "2026-03-24",
        "publisher": "GOV.UK",
        "person": {
            "person_id": "person:gb:gareth-davies",
            "canonical_name": "Gareth Davies",
            "published_name": "Gareth Davies CB",
            "position": "Permanent Secretary, Home Office",
            "variant": "Gareth Davies CB",
        },
        "organisation": {
            "organisation_id": "org:gb:home-office",
            "name": "Home Office",
            "type": "government_body",
        },
    },
    {
        "country": "gb",
        "url": "https://www.gov.uk/government/news/tom-riordan-appointed-as-new-permanent-secretary-ministry-of-housing-communities-and-local-government",
        "source_id": "gb-govuk-news",
        "document_id": "DOC-GB-0055",
        "record_uid": "GB-2026-APPT-002",
        "title": "Tom Riordan Appointed as New Permanent Secretary, Ministry of Housing, Communities and Local Government",
        "published": "2026-09-08",
        "publisher": "GOV.UK",
        "person": {
            "person_id": "person:gb:tom-riordan",
            "canonical_name": "Tom Riordan",
            "published_name": "Tom Riordan",
            "position": "Permanent Secretary, Ministry of Housing, Communities and Local Government",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:gb:ministry-of-housing-communities-and-local-government",
            "name": "Ministry of Housing, Communities and Local Government",
            "type": "government_body",
        },
    },
    {
        "country": "gb",
        "url": "https://www.gov.uk/government/news/clara-swinson-appointed-as-second-permanent-secretary-at-the-ministry-of-justice",
        "source_id": "gb-govuk-news",
        "document_id": "DOC-GB-0056",
        "record_uid": "GB-2026-APPT-003",
        "title": "Clara Swinson appointed as Second Permanent Secretary at the Ministry of Justice",
        "published": "2026-03-11",
        "publisher": "GOV.UK",
        "person": {
            "person_id": "person:gb:clara-swinson",
            "canonical_name": "Clara Swinson",
            "published_name": "Clara Swinson",
            "position": "Second Permanent Secretary, Ministry of Justice",
            "variant": None,
        },
        "organisation": {
            "organisation_id": "org:gb:ministry-of-justice",
            "name": "Ministry of Justice",
            "type": "government_body",
        },
    },
]


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read()
            time.sleep(0.8)
            return body
        except OSError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")


def normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_of(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return normalise(html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw)))


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


def extract_body(country: str, raw: str) -> str:
    if country == "mv":
        return text_of(
            re.search(r'<div class="article-body">(.*?)</div>', raw, re.S).group(1)
        )
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S):
        try:
            structured = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(structured, dict) and structured.get("articleBody"):
            return text_of(structured["articleBody"])
    raise RuntimeError("articleBody not found")


def main() -> int:
    by_country: dict[str, dict[str, list[dict]]] = {}
    for country in {item["country"] for item in APPOINTMENTS}:
        base = ROOT / "data" / country
        by_country[country] = {
            "records": read_ndjson(base / "records" / "records.ndjson"),
            "documents": read_ndjson(base / "sources" / "documents.ndjson"),
            "organisations": read_ndjson(base / "entities" / "organisations.ndjson"),
            "people": read_ndjson(base / "entities" / "people.ndjson"),
            "variants": read_ndjson(base / "entities" / "name-variants.ndjson"),
            "registry": read_ndjson(base / "sources" / "registry.ndjson"),
        }

    cache: dict[str, tuple[bytes, str]] = {}
    for item in APPOINTMENTS:
        url = item["url"]
        if url not in cache:
            raw_bytes = fetch(url)
            cache[url] = (raw_bytes, extract_body(item["country"], raw_bytes.decode("utf-8", "replace")))
        raw_bytes, body = cache[url]
        title = item["title"]
        text = normalise(f"{title} | {body}")
        source_sha = hashlib.sha256(raw_bytes).hexdigest()
        data = by_country[item["country"]]

        document = {
            "document_id": item["document_id"],
            "country_code": item["country"].upper(),
            "source_id": item["source_id"],
            "official_url": url,
            "retrieved_at": TODAY.isoformat(),
            "content_type": "text/html",
            "language": "en",
            "title": title,
            "publisher": item["publisher"],
            "publication_date": item["published"],
            "source_bytes": len(raw_bytes),
            "source_sha256": source_sha,
            "checksum_scope": "source_response",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        person = item["person"]
        organisation = item["organisation"]
        excerpt = text[: 400]
        record = {
            "uid": item["record_uid"],
            "record_type": "appointment",
            "title": title,
            "summary": None,
            "issue_id": None,
            "publication_date": item["published"],
            "language": "en",
            "issuing_organisation_name": organisation["name"],
            "people": [
                {
                    "person_id": person["person_id"],
                    "published_name": person["published_name"],
                    "position": person["position"],
                    "position_kind": "appointment",
                    "organisation_ids": [organisation["organisation_id"]],
                }
            ],
            "organisation_ids": [organisation["organisation_id"]],
            "location": "Maldives" if item["country"] == "mv" else "United Kingdom",
            "keywords": ["appointment", "public office"],
            "tender": None,
            "regulation": None,
            "notice": None,
            "source": {
                "kind": "html",
                "pdf_page": None,
                "printed_page": None,
                "document_id": item["document_id"],
                "excerpt": excerpt,
                "official_url": url,
                "sha256": source_sha,
                "checksum_scope": "source_response",
                "retrieved_at": TODAY.isoformat(),
            },
        }
        person_entity = {
            "person_id": person["person_id"],
            "country_code": item["country"].upper(),
            "canonical_name": person["canonical_name"],
            "identity_status": "operator_verified",
            "verified_at": TODAY.isoformat(),
            "basis": f"Identity reviewed against the official appointment announcement {url} "
            f"published {item['published']} and retrieved {TODAY.isoformat()}.",
        }
        organisation_entity = {
            "organisation_id": organisation["organisation_id"],
            "country_code": item["country"].upper(),
            "name": organisation["name"],
            "type": organisation["type"],
            "aliases": [],
            "identity_status": "operator_verified",
            "verified_at": TODAY.isoformat(),
            "basis": f"Named in the official appointment announcement {url} retrieved {TODAY.isoformat()}.",
        }

        data["records"] = [row for row in data["records"] if row["uid"] != item["record_uid"]]
        data["documents"] = [
            row for row in data["documents"] if row["document_id"] != item["document_id"]
        ]
        data["people"] = [
            row for row in data["people"] if row["person_id"] != person["person_id"]
        ]
        data["organisations"] = [
            row
            for row in data["organisations"]
            if row["organisation_id"] != organisation["organisation_id"]
        ]
        data["records"].append(record)
        data["documents"].append(document)
        data["people"].append(person_entity)
        data["organisations"].append(organisation_entity)
        if person["variant"]:
            variant_id = f"VAR-{item['country'].upper()}-{item['record_uid'].rsplit('-', 1)[-1]}"
            data["variants"] = [
                row for row in data["variants"] if row["variant_id"] != variant_id
            ]
            data["variants"].append(
                {
                    "variant_id": variant_id,
                    "person_id": person["person_id"],
                    "name": person["variant"],
                    "verification": "operator_verified",
                    "basis": f"Name form printed in the cited announcement; matched to the verified identity. Source {url}.",
                    "reviewed_at": TODAY.isoformat(),
                    "source_record_uids": [item["record_uid"]],
                }
            )
        print(f"{item['record_uid']}: {person['published_name']} — {person['position'][:70]}")

    registry_entries = {
        "mv": {
            "source_id": "mv-presidency",
            "country_code": "MV",
            "organisation": "The President's Office, Maldives",
            "publication_type": "public_notice",
            "title": "The President's Office — Press Releases",
            "official_url": "https://presidency.gov.mv/Press",
            "formats": ["html"],
            "languages": ["en", "dv"],
            "access_method": "Official press release pages",
            "reuse_restrictions": "Official government publication. Appointment records quote a short excerpt and link to the release; personal data beyond the published appointment is excluded.",
            "access_status": "verified",
            "adapter": None,
            "records_ingested": 4,
            "last_checked": TODAY.isoformat(),
            "notes": "Verified appointment announcements only; no inference of current office beyond the release date.",
        },
        "gb": {
            "source_id": "gb-govuk-news",
            "country_code": "GB",
            "organisation": "UK Government",
            "publication_type": "public_notice",
            "title": "GOV.UK — Government news and communications",
            "official_url": "https://www.gov.uk/government/news",
            "formats": ["html"],
            "languages": ["en"],
            "access_method": "Official GOV.UK announcement pages",
            "reuse_restrictions": "Crown copyright. Records quote a short excerpt under the Open Government Licence and link to the official announcement.",
            "access_status": "verified",
            "adapter": None,
            "records_ingested": 3,
            "last_checked": TODAY.isoformat(),
            "notes": "Senior public appointments announced by the Cabinet Secretary; historical role only.",
        },
    }
    for country, data in by_country.items():
        entry = registry_entries[country]
        data["registry"] = [row for row in data["registry"] if row["source_id"] != entry["source_id"]]
        data["registry"].append(entry)
        base = ROOT / "data" / country
        write_ndjson(base / "records" / "records.ndjson", data["records"], "uid")
        write_ndjson(base / "sources" / "documents.ndjson", data["documents"], "document_id")
        write_ndjson(base / "entities" / "people.ndjson", data["people"], "person_id")
        write_ndjson(base / "entities" / "organisations.ndjson", data["organisations"], "organisation_id")
        write_ndjson(base / "entities" / "name-variants.ndjson", data["variants"], "variant_id")
        write_ndjson(base / "sources" / "registry.ndjson", data["registry"], "source_id")
    print(f"imported {len(APPOINTMENTS)} appointment records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
