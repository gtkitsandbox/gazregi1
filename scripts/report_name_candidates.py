"""Report possible name matches for operator review. Never merge identities."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from content.models import NameVariant, PersonEntity, normalise_name  # noqa: E402


def read_ndjson(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--country", default="lk")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "name-candidates.ndjson")
    args = parser.parse_args()

    country_dir = args.data_root / args.country
    people = [PersonEntity.model_validate(row) for row in read_ndjson(country_dir / "entities" / "people.ndjson")]
    variants = [NameVariant.model_validate(row) for row in read_ndjson(country_dir / "entities" / "name-variants.ndjson")]
    records = read_ndjson(country_dir / "records" / "records.ndjson")

    names: dict[str, set[str]] = defaultdict(set)
    for person in people:
        names[normalise_name(person.canonical_name)].add(person.person_id)
    for variant in variants:
        names[normalise_name(variant.name)].add(variant.person_id)

    record_names: dict[str, list[str]] = defaultdict(list)
    for record in records:
        for person in record.get("people", []):
            record_names[normalise_name(person["published_name"])].append(record["uid"])

    candidates = []
    for normalised, person_ids in sorted(names.items()):
        if len(person_ids) > 1:
            candidates.append(
                {
                    "kind": "same_normalised_name",
                    "normalised_name": normalised,
                    "person_ids": sorted(person_ids),
                    "record_uids": sorted(set(record_names.get(normalised, []))),
                    "action": "operator review required; identities remain separate",
                }
            )
    for normalised, uids in sorted(record_names.items()):
        linked = sorted({person_id for normalised_name, ids in names.items() if normalised_name == normalised for person_id in ids})
        if len(linked) > 1:
            candidates.append(
                {
                    "kind": "name_used_by_multiple_identities",
                    "normalised_name": normalised,
                    "person_ids": linked,
                    "record_uids": sorted(set(uids)),
                    "action": "operator review required; no record is moved automatically",
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for candidate in candidates:
            output.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    try:
        output_label = args.output.relative_to(ROOT)
    except ValueError:
        output_label = args.output
    print(f"Wrote {len(candidates)} name candidate(s) to {output_label}")
    print("No identity was merged. This report is advisory only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
