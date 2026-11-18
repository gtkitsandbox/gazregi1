"""Import one verified Japanese government-procurement notice from Kanpō.

The official procurement edition is a PDF.  PyMuPDF text is stored as a
transformed snapshot (the checksum is of the original PDF, not the extracted
text), and the notice keeps its Japanese title verbatim.  Closing dates that
could not be read reliably from the PDF are recorded as unknown rather than
guessed.

    python scripts/import_jp_notice.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
JP = ROOT / "data" / "jp"
TODAY = date.today()
PDF_URL = "https://www.kanpo.go.jp/20261118/20261118c00213/pdf/20261118c00213full00010040.pdf"


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


def main() -> int:
    request = urllib.request.Request(
        PDF_URL, headers={"User-Agent": "GazetteRegistry/1.0 (+https://gazetteregistry.com)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    document_file = Path("/tmp/kanpo_proc.pdf")
    document_file.write_bytes(raw)
    pdf = pymupdf.open(document_file)
    page_text = normalise(pdf[0].get_text())
    title = "熊本第二合同庁舎ほか５庁舎の電力需給契約"
    excerpt = normalise(
        "購入等件名及び予定数量 熊本第二合同庁 舎ほか５庁舎の電力需給契約"
    )
    if excerpt not in page_text:
        raise RuntimeError("excerpt not found in extracted PDF text")

    document = {
        "document_id": "DOC-JP-0001",
        "country_code": "JP",
        "source_id": "jp-kanpo",
        "official_url": PDF_URL,
        "retrieved_at": TODAY.isoformat(),
        "content_type": "application/pdf",
        "language": "ja",
        "title": "政府調達 第213号（令和8年11月18日）",
        "publisher": "国立印刷局",
        "publication_date": "2026-11-18",
        "source_bytes": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "checksum_scope": "transformed_snapshot",
        "text": page_text,
        "text_sha256": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
    }
    organisation = {
        "organisation_id": "org:jp:kumamoto-legal-affairs-bureau",
        "country_code": "JP",
        "name": "熊本地方法務局",
        "type": "government_body",
        "aliases": ["Kumamoto Legal Affairs Bureau"],
        "identity_status": "operator_verified",
        "verified_at": TODAY.isoformat(),
        "basis": f"Named as the procuring agency in Kanpō government procurement edition, {PDF_URL}, retrieved {TODAY.isoformat()}.",
    }
    record = {
        "uid": "JP-2026-TEND-001",
        "record_type": "tender",
        "title": title,
        "summary": None,
        "issue_id": None,
        "publication_date": "2026-11-18",
        "language": "ja",
        "issuing_organisation_name": "熊本地方法務局",
        "people": [],
        "organisation_ids": [organisation["organisation_id"]],
        "location": "熊本県",
        "keywords": ["政府調達", "入札公告", "電力"],
        "tender": {
            "reference": "第１号",
            "issuer_organisation_id": organisation["organisation_id"],
            "sector": "goods",
            "opportunity_kind": "tender",
            "status": "unknown",
            "source_status": "入札公告",
            "status_as_of": TODAY.isoformat(),
            "location": "熊本県",
            "closing_date": None,
            "closing_time": None,
            "document_deadline": None,
            "bid_security_lkr": None,
            "bid_security": None,
            "currency": "JPY",
            "awarded_to": None,
            "award_amount": None,
            "award_date": None,
        },
        "regulation": None,
        "notice": None,
        "source": {
            "kind": "text",
            "pdf_page": None,
            "printed_page": None,
            "document_id": "DOC-JP-0001",
            "excerpt": excerpt,
            "official_url": PDF_URL,
            "sha256": document["source_sha256"],
            "checksum_scope": "transformed_snapshot",
            "retrieved_at": TODAY.isoformat(),
        },
    }

    records = [row for row in read_ndjson(JP / "records" / "records.ndjson") if row["uid"] != record["uid"]]
    records.append(record)
    documents = [
        row
        for row in read_ndjson(JP / "sources" / "documents.ndjson")
        if row["document_id"] != document["document_id"]
    ]
    documents.append(document)
    organisations = [
        row
        for row in read_ndjson(JP / "entities" / "organisations.ndjson")
        if row["organisation_id"] != organisation["organisation_id"]
    ]
    organisations.append(organisation)
    registry = read_ndjson(JP / "sources" / "registry.ndjson")
    for entry in registry:
        if entry["source_id"] == "jp-kanpo":
            entry["records_ingested"] = 1
            entry["notes"] = (
                "Daily index and PDF editions are reachable. One procurement notice was extracted "
                "from the official PDF in Phase 1D; the notices use Japanese text and closing dates "
                "that could not be read reliably are recorded as unknown."
            )
    write_ndjson(JP / "records" / "records.ndjson", records, "uid")
    write_ndjson(JP / "sources" / "documents.ndjson", documents, "document_id")
    write_ndjson(JP / "entities" / "organisations.ndjson", organisations, "organisation_id")
    write_ndjson(JP / "sources" / "registry.ndjson", registry, "source_id")

    country_path = JP / "country.json"
    country = json.loads(country_path.read_text(encoding="utf-8"))
    country["coverage_status"] = "partial"
    country_path.write_text(json.dumps(country, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {record['uid']}: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
