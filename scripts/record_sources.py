"""Record SHA-256 provenance for local PDF extraction inputs.

New PDFs stay in raw/ locally and are ignored by Git.  This registry preserves
the checksum, issue mapping and official URL (when known) in tracked data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_registry(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["source_file"]] = row
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--raw-root", type=Path, default=ROOT / "raw")
    args = parser.parse_args()

    issues_by_file: dict[str, tuple[str, dict[str, object]]] = {}
    for issue_path in sorted(args.data_root.glob("*/*/*/issue.json")):
        country_code = issue_path.parents[2].name
        data = json.loads(issue_path.read_text(encoding="utf-8"))
        source_file = str(data["source_file"])
        if source_file in issues_by_file:
            raise SystemExit(f"Duplicate source_file {source_file} across issues")
        issues_by_file[source_file] = (country_code, data)

    rows_by_country: dict[str, list[dict[str, object]]] = defaultdict(list)
    skipped = 0
    for pdf in sorted(args.raw_root.glob("*.pdf")):
        match = issues_by_file.get(pdf.name)
        if match is None:
            print(f"SKIP: {pdf.name} has no matching extracted issue")
            skipped += 1
            continue
        country_code, issue = match
        registry_path = args.data_root / country_code / "sources" / "sources.ndjson"
        previous = read_registry(registry_path).get(pdf.name, {})
        rows_by_country[country_code].append(
            {
                "source_file": pdf.name,
                "issue_id": issue["issue_id"],
                "sha256": sha256(pdf),
                "bytes": pdf.stat().st_size,
                "official_url": issue.get("source_url") or previous.get("official_url"),
                "checked_at": date.today().isoformat(),
            }
        )

    for country_code, rows in sorted(rows_by_country.items()):
        registry_path = args.data_root / country_code / "sources" / "sources.ndjson"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with registry_path.open("w", encoding="utf-8") as output:
            for row in rows:
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Recorded {len(rows)} source document(s) in {registry_path.relative_to(ROOT)}")
    if skipped:
        print(f"Skipped {skipped} unmatched PDF(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
