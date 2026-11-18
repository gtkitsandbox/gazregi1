#!/usr/bin/env python3
"""Run a source adapter and write normalised records, snapshots and registry rows.

Usage:
    python scripts/ingest.py --sync-registry
    python scripts/ingest.py --country gb --source gb-the-gazette --limit 10
    python scripts/ingest.py --country us --all --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.content.models import SourceRegistryEntry  # noqa: E402
from src.ingest.adapters import ADAPTERS  # noqa: E402
from src.ingest.core import Dataset  # noqa: E402

CONFIG = ROOT / "config" / "sources-intl.json"
DATA = ROOT / "data"


def load_definitions() -> list[dict]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]


def to_registry(definition: dict, ingested: int | None = None) -> SourceRegistryEntry:
    payload = dict(definition)
    payload["records_ingested"] = ingested if ingested is not None else payload.get("records_ingested", 0)
    payload.setdefault("last_checked", date.today().isoformat())
    return SourceRegistryEntry(**payload)


def sync_registry(definitions: list[dict]) -> None:
    by_country: dict[str, list[dict]] = {}
    for definition in definitions:
        by_country.setdefault(definition["country_code"].lower(), []).append(definition)
    for country, rows in sorted(by_country.items()):
        dataset = Dataset(DATA, country)
        for definition in rows:
            ingested = sum(
                1
                for row in dataset.records.values()
                if row.source.document_id
                and row.source.document_id in dataset.documents
                and dataset.documents[row.source.document_id].source_id == definition["source_id"]
            )
            dataset.set_registry(to_registry(definition, ingested))
        dataset.save()
        print(f"registry {country}: {len(rows)} source(s)")


def run_one(definition: dict, limit: int) -> int:
    adapter_name = definition.get("adapter")
    if not adapter_name or adapter_name not in ADAPTERS:
        print(f"{definition['source_id']}: no adapter (status {definition['access_status']})")
        return 0
    country = definition["country_code"].lower()
    dataset = Dataset(DATA, country)
    print(f"{definition['source_id']}: {adapter_name} limit={limit}")
    try:
        added = ADAPTERS[adapter_name](dataset, limit=limit)
    except Exception:
        traceback.print_exc()
        print(f"{definition['source_id']}: FAILED, no data written")
        return 0
    ingested = sum(
        1
        for row in dataset.records.values()
        if row.source.document_id
        and dataset.documents[row.source.document_id].source_id == definition["source_id"]
    )
    definition = {**definition, "records_ingested": ingested, "last_checked": date.today().isoformat()}
    dataset.set_registry(to_registry(definition, ingested))
    dataset.save()
    print(f"{definition['source_id']}: added {added}, stored {ingested} record(s)")
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--country")
    parser.add_argument("--source")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--all", action="store_true", help="run every adapter for the country")
    parser.add_argument("--sync-registry", action="store_true")
    args = parser.parse_args()

    definitions = load_definitions()
    if args.sync_registry:
        sync_registry(definitions)
        return 0
    if not args.country:
        parser.error("--country is required unless --sync-registry is used")
    selected = [
        row
        for row in definitions
        if row["country_code"].lower() == args.country.lower()
        and (args.all or row["source_id"] == args.source)
    ]
    if not selected:
        print("no matching source")
        return 1
    total = 0
    for definition in selected:
        total += run_one(definition, args.limit)
    print(f"total added: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
