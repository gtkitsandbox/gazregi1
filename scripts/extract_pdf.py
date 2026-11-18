"""Extract searchable, page-level records from a Gazette PDF."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pymupdf


FILENAME_PATTERN = re.compile(r"Gazette-(\d{4})-(\d{2})-(\d{2})-(.+)\.pdf$", re.IGNORECASE)
GAZETTE_NUMBER_PATTERN = re.compile(r"\bNo\.\s*([\d,]+)", re.IGNORECASE)
HEADER_PATTERN = re.compile(r"GAZETTE OF THE DEMOCRATIC SOCIALIST REPUBLIC", re.IGNORECASE)


def extract_issue(
    pdf_path: Path,
    output_root: Path,
    source_url: str | None = None,
    country_code: str = "lk",
    *,
    gazette_number: str | None = None,
    publication_date: str | None = None,
    edition: str | None = None,
    gazette_type: str | None = None,
    language: str | None = None,
) -> Path:
    match = FILENAME_PATTERN.fullmatch(pdf_path.name)
    if match is not None:
        year, month, day, file_edition = match.groups()
        edition = edition or file_edition
        publication_date = publication_date or f"{year}-{month}-{day}"
    if publication_date is None:
        raise ValueError(
            "Expected a Gazette-YYYY-MM-DD-edition.pdf filename or an explicit "
            f"--publication-date: {pdf_path.name}"
        )
    try:
        parsed_date = datetime.strptime(publication_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--publication-date must be YYYY-MM-DD") from exc
    year = f"{parsed_date.year:04d}"
    edition = edition or "E"

    country_code = country_code.strip().lower()
    if not re.fullmatch(r"[a-z]{2}", country_code):
        raise ValueError("--country must be a two-letter country code")
    document = pymupdf.open(pdf_path)
    first_page_text = cast(str, document.load_page(0).get_text("text"))
    if gazette_number is None:
        number_match = GAZETTE_NUMBER_PATTERN.search(first_page_text)
        if number_match is not None:
            gazette_number = number_match.group(1).replace(",", "")
        else:
            leading_match = re.match(r"\s*(\d{4,6})\s*[.\n]", first_page_text)
            if leading_match is not None:
                gazette_number = leading_match.group(1)
    if gazette_number is None:
        raise ValueError(
            f"Could not determine Gazette number from {pdf_path.name}; "
            "pass --gazette-number copied from the document"
        )

    issue_id = f"{country_code.upper()}-{year}-{gazette_number}"
    output_dir = output_root / country_code / year / f"{publication_date}-{gazette_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    issue = {
        "issue_id": issue_id,
        "country": country_code.upper(),
        "gazette_no": gazette_number,
        "gazette_type": gazette_type
        or ("regular" if edition.lower() == "e" else "extraordinary"),
        "edition": edition,
        "publication_date": publication_date,
        "source_url": source_url,
        "source_file": pdf_path.name,
        "page_count": len(document),
        "parser_version": "0.1.0",
        "extraction_method": "pymupdf",
        "extracted_at": extracted_at,
    }

    page_records: list[dict[str, object]] = []
    text_records: list[dict[str, str]] = []
    empty_pages: list[int] = []
    for index in range(document.page_count):
        page = document.load_page(index)
        text = cast(str, page.get_text("text")).strip()
        if not text:
            empty_pages.append(index + 1)
            continue

        physical_page = index + 1
        printed_page = _printed_page_number(text)
        page_uid = f"{issue_id}-PAGE-{physical_page:03d}"
        title = f"Gazette {gazette_number} - page {printed_page or physical_page}"
        page_records.append(
            {
                "uid": page_uid,
                "issue_id": issue_id,
                "physical_pdf_page": physical_page,
                "printed_page": printed_page,
                "section": None,
                "category": "UNCLASSIFIED",
                "subcategory": None,
                "title": title,
                "summary": None,
                "keywords": [],
                "source": {
                    "url": source_url,
                    "gazette_no": gazette_number,
                    "page_start": printed_page,
                    "page_end": printed_page,
                    "language": language
                    or ("en" if edition.upper().startswith("E") else None),
                },
            }
        )
        text_records.append({"uid": page_uid, "text": text})

    if empty_pages:
        print(
            f"warning: {len(empty_pages)} of {len(document)} pages have no extractable "
            f"text layer (pages {', '.join(map(str, empty_pages))}); scanned pages require "
            "OCR or manual transcription before records can be curated",
            file=sys.stderr,
        )
    if not page_records:
        raise ValueError(f"No searchable text found in {pdf_path.name}; OCR is not enabled")

    _write_json(output_dir / "issue.json", issue)
    _write_jsonl(output_dir / "pages.ndjson", page_records)
    with gzip.open(output_dir / "text.jsonl.gz", "wt", encoding="utf-8") as output:
        for record in text_records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    return output_dir


def _printed_page_number(text: str) -> int | None:
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if HEADER_PATTERN.search(line):
            for candidate in lines[index + 1 : index + 5]:
                if candidate.isdigit():
                    return int(candidate)
            break
    return None


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to an official Gazette PDF")
    parser.add_argument("--output", type=Path, default=Path("data"), help="Output data directory")
    parser.add_argument("--source-url", help="Verified official URL for this Gazette PDF")
    parser.add_argument("--country", default="lk", help="Two-letter country code (default: lk)")
    parser.add_argument(
        "--gazette-number",
        help="Gazette number copied from the document when it cannot be detected automatically",
    )
    parser.add_argument(
        "--publication-date",
        help="Publication date YYYY-MM-DD for filenames that do not follow the Gazette convention",
    )
    parser.add_argument("--edition", help="Edition code, for example E or Eii")
    parser.add_argument(
        "--gazette-type",
        help="Document type when it is not regular or extraordinary, for example supplement",
    )
    parser.add_argument("--language", help="ISO language code when it is not implied by the edition")
    args = parser.parse_args()

    output_dir = extract_issue(
        args.pdf,
        args.output,
        args.source_url,
        args.country,
        gazette_number=args.gazette_number,
        publication_date=args.publication_date,
        edition=args.edition,
        gazette_type=args.gazette_type,
        language=args.language,
    )
    print(f"Extracted Gazette pages to {output_dir}")


if __name__ == "__main__":
    main()