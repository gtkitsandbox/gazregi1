"""Build the production site or the isolated designer preview."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from content.build import build_site  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Build the non-indexable designer preview")
    parser.add_argument("--data-root", type=Path, help="Dataset root (default: data/ or demo/)")
    parser.add_argument("--config", type=Path, help="Site config path")
    parser.add_argument("--output", type=Path, help="Output directory")
    parser.add_argument("--raw-root", type=Path, help="Local extraction input directory")
    parser.add_argument("--site-url", help="Canonical site origin")
    args = parser.parse_args()

    preview = args.preview
    data_root = args.data_root or (ROOT / ("demo" if preview else "data"))
    config = args.config or (ROOT / "config" / ("preview.json" if preview else "site.json"))
    output = args.output or (ROOT / ("dist-preview" if preview else "dist"))
    raw_root = None if preview else (args.raw_root or ROOT / "raw")

    report = build_site(
        data_root=data_root,
        config_path=config,
        output_dir=output,
        raw_root=raw_root,
        preview=preview,
        site_url=args.site_url,
    )
    label = "Designer preview" if report.preview else "Production site"
    print(f"{label} generated in {report.output_dir}")
    print(
        f"  issues={report.issues} pages={report.pages} records={report.records} "
        f"verified_people={report.people} organisations={report.organisations} "
        f"html_files={report.html_files}"
    )
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
