"""Phase 1D corpus repair.

Normalises provenance metadata across the existing international records and
removes records that re-publish the same source document under two record
types or twice within one source.

The script is deterministic apart from reading existing data: it does not fetch
anything and it never invents a fact.  Run it from the repository root:

    python scripts/phase1d_repair.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCOPE_BY_SOURCE = {
    "au-legislation-register": "source_response",
    "au-legislation-notices": "source_response",
    "bd-egp": "original_source",
    "ca-canada-gazette": "original_source",
    "ca-canadabuys": "source_response",
    "de-bgbl": "original_source",
    "de-ted": "source_response",
    "gb-find-a-tender": "source_response",
    "gb-the-gazette": "original_source",
    "ie-ted": "source_response",
    "ke-ppip": "source_response",
    "nl-ted": "source_response",
    "nz-gets": "original_source",
    "sg-gebiz": "source_response",
    "us-federal-register": "source_response",
    "us-grants-gov": "source_response",
    "za-etenders": "source_response",
}

TYPE_PRIORITY = {"tender": 1, "public_notice": 2, "regulation": 3}


def read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_ndjson(path: Path, rows: list[dict], key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: row[key])
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    path.write_text(text, encoding="utf-8")


def normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def choose_keeper(rows: list[dict]) -> dict:
    return sorted(
        rows,
        key=lambda row: (
            -TYPE_PRIORITY.get(row["record_type"], 0),
            row["uid"],
        ),
    )[0]


def repair_country(country_dir: Path) -> tuple[int, int]:
    records_path = country_dir / "records" / "records.ndjson"
    documents_path = country_dir / "sources" / "documents.ndjson"
    records = read_ndjson(records_path)
    documents = read_ndjson(documents_path)
    if not records:
        return 0, 0

    by_document: dict[str, dict] = {doc["document_id"]: doc for doc in documents}
    removed = 0

    # Remove exact document+title duplicates across record types.
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        document_id = record.get("source", {}).get("document_id")
        if document_id:
            groups[(document_id, normalise(record["title"]))].append(record)
    dropped: set[str] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        keeper = choose_keeper(group)
        for record in group:
            if record["uid"] != keeper["uid"]:
                dropped.add(record["uid"])
                removed += 1
    records = [record for record in records if record["uid"] not in dropped]

    # Remove duplicate tender references within the same source document.
    reference_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in records:
        tender = record.get("tender")
        document_id = record.get("source", {}).get("document_id")
        if document_id and tender:
            reference_groups[(document_id, normalise(tender["reference"]))].append(record)
    dropped = set()
    for group in reference_groups.values():
        if len(group) < 2:
            continue
        keeper = choose_keeper(group)
        for record in group:
            if record["uid"] != keeper["uid"]:
                dropped.add(record["uid"])
                removed += 1
    records = [record for record in records if record["uid"] not in dropped]

    for document in documents:
        scope = SCOPE_BY_SOURCE.get(document.get("source_id", ""), "transformed_snapshot")
        if document.get("source_id", "").startswith(("xx-", "yy-", "zz-")):
            scope = "transformed_snapshot"
        document["checksum_scope"] = scope
        document["text_sha256"] = hashlib.sha256(
            document["text"].encode("utf-8")
        ).hexdigest()

    for record in records:
        tender = record.get("tender")
        if tender is not None and "status_as_of" not in tender:
            as_of = (
                record.get("source", {}).get("retrieved_at")
                or record.get("publication_date")
            )
            tender["status_as_of"] = as_of
        document_id = record.get("source", {}).get("document_id")
        document = by_document.get(document_id) if document_id else None
        if document is not None:
            record["source"]["checksum_scope"] = document["checksum_scope"]

    write_ndjson(records_path, records, "uid")
    write_ndjson(documents_path, documents, "document_id")
    return len(records), removed


def main() -> int:
    total_records = 0
    total_removed = 0
    for country_dir in sorted(path for path in DATA.iterdir() if path.is_dir()):
        count, removed = repair_country(country_dir)
        if count:
            print(f"{country_dir.name}: {count} records, {removed} duplicate(s) removed")
            total_records += count
            total_removed += removed
    print(f"total: {total_records} records, {total_removed} duplicate(s) removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
