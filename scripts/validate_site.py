"""Validate a generated build, deployment limits and content provenance."""

from __future__ import annotations

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from content.build import _person_path, _record_path  # noqa: E402
from content.loader import ContentValidationError, load_site  # noqa: E402
from content.models import CuratedRecord  # noqa: E402

HARD_FILE_LIMIT = 20_000
TARGET_FILE_LIMIT = 15_000
MAX_ASSET_BYTES = 25 * 1024 * 1024


@dataclass
class HtmlFacts:
    title: str = ""
    description: str = ""
    robots: str = ""
    canonicals: list[str] = field(default_factory=list)
    h1_count: int = 0
    jsonld: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = HtmlFacts()
        self._in_title = False
        self._in_jsonld = False
        self._jsonld_buffer: list[str] = []
        self._title_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = values.get("name", "").lower()
            if name == "description":
                self.facts.description = values.get("content", "")
            elif name == "robots":
                self.facts.robots = values.get("content", "")
        elif tag == "link":
            if "canonical" in values.get("rel", "").lower():
                self.facts.canonicals.append(values.get("href", ""))
            if values.get("href"):
                self.facts.links.append((tag, values["href"]))
        elif tag == "h1":
            self.facts.h1_count += 1
        elif tag == "script":
            if values.get("type") == "application/ld+json":
                self._in_jsonld = True
                self._jsonld_buffer = []
        if tag in {"a", "img", "script", "source"}:
            for key in ("href", "src"):
                if values.get(key):
                    self.facts.links.append((tag, values[key]))
        if tag == "form" and values.get("action"):
            self.facts.links.append((tag, values["action"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.facts.title = "".join(self._title_buffer).strip()
        elif tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.facts.jsonld.append("".join(self._jsonld_buffer))
        elif tag == "h1":
            pass

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buffer.append(data)
        if self._in_jsonld:
            self._jsonld_buffer.append(data)


def parse_html(path: Path) -> HtmlFacts:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser.facts


def resolve_internal(dist: Path, base_file: Path, raw_url: str) -> Path | None:
    url = raw_url.strip()
    if not url or url.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    if path.startswith("/"):
        candidate = dist / path.lstrip("/")
    else:
        candidate = base_file.parent / path
    if path.endswith("/") or candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def display_path(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def build_validation_report(
    *,
    preview: bool,
    output_dir: Path,
    site_url: str,
) -> tuple[list[str], list[str], dict[str, object]]:
    errors: list[str] = []
    warnings: list[str] = []
    report: dict[str, object] = {}

    if not output_dir.exists():
        return [f"{output_dir}: output directory does not exist"], warnings, report

    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)
    largest = max(files, key=lambda path: path.stat().st_size)
    search_dir = output_dir / "pagefind"
    search_bytes = (
        sum(path.stat().st_size for path in search_dir.rglob("*") if path.is_file())
        if search_dir.exists()
        else 0
    )
    report["assets"] = len(files)
    report["bytes"] = total_bytes
    report["largest_file"] = (display_path(largest), largest.stat().st_size)
    report["search_bytes"] = search_bytes
    report["search_files"] = (
        sum(1 for path in search_dir.rglob("*") if path.is_file()) if search_dir.exists() else 0
    )

    if len(files) > HARD_FILE_LIMIT:
        errors.append(f"{len(files)} assets exceed the Cloudflare static asset limit of {HARD_FILE_LIMIT}")
    elif len(files) > TARGET_FILE_LIMIT:
        warnings.append(
            f"{len(files)} assets exceed the {TARGET_FILE_LIMIT}-file target; review Pagefind sharding before growth."
        )
    for path in files:
        if path.stat().st_size > MAX_ASSET_BYTES:
            errors.append(f"{display_path(path)} exceeds the 25 MiB static asset limit")
    pdfs = [path for path in files if path.suffix.lower() == ".pdf"]
    if pdfs:
        errors.append(f"PDF files must not be deployed: {display_path(pdfs[0])}")

    if not (search_dir / "pagefind.js").exists():
        errors.append("Pagefind index is missing; run pagefind --site on the output directory")
    if not (search_dir / "pagefind-entry.json").exists():
        errors.append("Pagefind entry metadata is missing")

    html_files = [path for path in files if path.suffix == ".html"]
    if not html_files:
        errors.append("No HTML files generated")
    indexed_html = 0
    broken: list[tuple[Path, str]] = []
    noindex_paths: list[str] = []
    jsonld_count = 0

    for path in html_files:
        facts = parse_html(path)
        relative = "/" + str(path.relative_to(output_dir)).replace("\\", "/")
        if not facts.title:
            errors.append(f"{display_path(path)}: missing title")
        if not facts.description:
            errors.append(f"{display_path(path)}: missing meta description")
        if len(facts.canonicals) != 1:
            errors.append(f"{display_path(path)}: expected exactly one canonical URL")
        if facts.h1_count != 1:
            errors.append(f"{display_path(path)}: expected exactly one h1 (found {facts.h1_count})")
        if not facts.robots:
            errors.append(f"{display_path(path)}: missing robots meta")
        if "noindex" in facts.robots.lower():
            noindex_paths.append(relative)
        for block in facts.jsonld:
            jsonld_count += 1
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{display_path(path)}: invalid JSON-LD: {exc}")
        text = path.read_text(encoding="utf-8")
        if "data-pagefind-body" in text:
            indexed_html += 1
        for _tag, url in facts.links:
            target = resolve_internal(output_dir, path, url)
            if target is not None and not target.exists():
                broken.append((path, url))

    report["html"] = len(html_files)
    report["indexed_html"] = indexed_html
    report["jsonld_blocks"] = jsonld_count
    report["noindex_pages"] = len(noindex_paths)
    if broken:
        for path, url in broken[:20]:
            errors.append(f"Broken internal link in {display_path(path)}: {url}")
        if len(broken) > 20:
            errors.append(f"... and {len(broken) - 20} more broken internal links")

    # Dataset validation and rendered-content checks.
    preview_mode = preview
    data_root = ROOT / ("demo" if preview_mode else "data")
    config_path = ROOT / "config" / ("preview.json" if preview_mode else "site.json")
    try:
        site = load_site(
            data_root=data_root,
            config_path=config_path,
            raw_root=None if preview_mode else ROOT / "raw",
            preview=preview_mode,
            site_url=site_url,
        )
    except ContentValidationError as exc:
        errors.extend(exc.errors)
        site = None

    if site is not None:
        for person in site.published_people:
            parts = person.person_id.split(":")
            path = output_dir / "people" / parts[1] / parts[2] / "index.html"
            if not path.exists():
                errors.append(f"Missing verified person page: {person.person_id}")
                continue
            page_text = html.unescape(path.read_text(encoding="utf-8"))
            if person.canonical_name not in page_text:
                errors.append(f"{person.person_id}: canonical name missing from generated HTML")
            if "not statements of current employment" not in page_text:
                errors.append(
                    f"{person.person_id}: historical/current position distinction missing"
                )
            for variant in site.verified_variants_for(person.person_id):
                if variant.name not in page_text:
                    errors.append(
                        f"{person.person_id}: verified name variant missing: {variant.name}"
                    )
            person_records = sorted(
                site.records_for_person(person.person_id),
                key=lambda record: (site.record_date(record) or date.min, record.uid),
            )
            positions = []
            for record in person_records:
                if record.title not in page_text:
                    errors.append(f"{person.person_id}: record {record.uid} missing from person page")
                else:
                    positions.append(page_text.index(record.title))
            if positions != sorted(positions):
                errors.append(f"{person.person_id}: record history is not chronological")
        for person in site.held_people:
            parts = person.person_id.split(":")
            if (output_dir / "people" / parts[1] / parts[2] / "index.html").exists():
                errors.append(f"Unverified person page was published: {person.person_id}")

        for record in site.records:
            path = output_dir / _record_path(record).strip("/") / "index.html"
            if not path.exists():
                errors.append(f"Missing record page for {record.uid}")
                continue
            text = html.unescape(path.read_text(encoding="utf-8"))
            if record.source.excerpt not in text:
                errors.append(f"{record.uid}: source excerpt missing from generated HTML")
            if record.record_type == "tender" and record.tender is not None:
                if record.tender.reference not in text:
                    errors.append(f"{record.uid}: tender reference missing from generated HTML")

        for issue in site.issues:
            issue_path = output_dir / "gazettes" / issue.issue.issue_id / "index.html"
            if not issue_path.exists():
                errors.append(f"Missing Gazette issue page: {issue.issue.issue_id}")

        for country in site.countries:
            code = country.config.country_code.lower()
            country_path = output_dir / "countries" / code / "index.html"
            if not country_path.exists():
                errors.append(f"Missing country page: /countries/{code}/")
                continue
            country_text = html.unescape(country_path.read_text(encoding="utf-8"))
            if country.config.name not in country_text:
                errors.append(f"/countries/{code}/: country name missing")
            for record in country.records:
                if record.source.kind != "pdf":
                    document = site.document_for(record.source.document_id or "")
                    if str(record.source.official_url) != str(document.official_url):
                        errors.append(f"{record.uid}: official URL differs from document snapshot")
                    if record.source.sha256 != document.source_sha256:
                        errors.append(f"{record.uid}: checksum differs from document snapshot")
            record_path = output_dir / "countries" / code / "index.html"
            if record_path.exists() and f">{len(country.records)}<" not in record_path.read_text(encoding="utf-8"):
                warnings.append(f"/countries/{code}/: record count not found as a standalone statistic")

        source_path = output_dir / "sources" / "index.html"
        if not source_path.exists():
            errors.append("Missing source registry page: /sources/")
        else:
            source_text = source_path.read_text(encoding="utf-8")
            for entry in site.source_registry:
                if f'id="source-{entry.source_id}"' not in source_text:
                    errors.append(f"/sources/: missing anchor for {entry.source_id}")

        for record in site.records:
            if record.source.kind == "pdf":
                continue
            document = site.document_for(record.source.document_id or "")
            if document.country_code != site.country_of_record(record).config.country_code:
                errors.append(f"{record.uid}: document country mismatch")

        # Deployment metadata
        if preview_mode:
            robots = (output_dir / "robots.txt").read_text(encoding="utf-8") if (output_dir / "robots.txt").exists() else ""
            if "Disallow: /" not in robots:
                errors.append("Preview robots.txt must disallow all crawling")
            if (output_dir / "sitemap.xml").exists():
                errors.append("Preview must not publish a sitemap")
            if (output_dir / "CNAME").exists():
                errors.append("Preview must not publish a CNAME")
            for path in html_files:
                facts = parse_html(path)
                if "noindex" not in facts.robots.lower():
                    errors.append(f"{display_path(path)}: preview page is not noindex")
            preview_text = "\n".join(path.read_text(encoding="utf-8") for path in html_files)
            for forbidden in ("gazetteregistry.com", "Sri Lanka"):
                if forbidden in preview_text:
                    errors.append(f"Preview contains production marker: {forbidden}")
            if "Designer preview" not in preview_text:
                errors.append("Designer preview banner is missing")
            for required in ("Nordmark", "Coralia"):
                if required not in preview_text:
                    errors.append(f"Preview multi-country coverage is missing: {required}")
        else:
            sitemap_path = output_dir / "sitemap.xml"
            if not sitemap_path.exists():
                errors.append("Production sitemap.xml is missing")
            else:
                try:
                    tree = ET.parse(sitemap_path)
                    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                    urls = [node.text or "" for node in tree.findall(".//s:loc", namespace)]
                    report["sitemap_urls"] = len(urls)
                    sitemap_url_set = set(urls)
                    for person in site.published_people:
                        person_url = site_url.rstrip("/") + _person_path(person)
                        if person_url not in sitemap_url_set:
                            errors.append(
                                f"{person.person_id}: verified person page missing from sitemap"
                            )
                    for url in urls:
                        if not url.startswith(site_url):
                            errors.append(f"Sitemap URL outside site origin: {url}")
                            continue
                        relative = urlsplit(url).path
                        candidate = output_dir / unquote(relative).lstrip("/")
                        if relative.endswith("/") or candidate.is_dir():
                            candidate = candidate / "index.html"
                        if not candidate.exists():
                            errors.append(f"Sitemap URL has no generated page: {url}")
                except ET.ParseError as exc:
                    errors.append(f"sitemap.xml is not valid XML: {exc}")
            robots = (output_dir / "robots.txt").read_text(encoding="utf-8") if (output_dir / "robots.txt").exists() else ""
            if "Sitemap:" not in robots:
                errors.append("Production robots.txt does not reference the sitemap")
            cname_path = output_dir / "CNAME"
            if not cname_path.exists():
                errors.append("Production CNAME is missing")
            production_text = "\n".join(path.read_text(encoding="utf-8") for path in html_files)
            for forbidden in (
                "Demo Republic",
                "demo-gazette",
                "DEMO/TEND",
                "A. Example",
                "preview.invalid",
                "XX-2099-9999",
                "Nordmark",
                "Coralia",
                "DEMO-YY-001",
                "example.invalid",
            ):
                if forbidden in production_text:
                    errors.append(f"Production build contains demonstration marker: {forbidden}")
            for path in html_files:
                facts = parse_html(path)
                if "noindex" not in facts.robots.lower():
                    continue
                relative_parts = path.relative_to(output_dir).parts
                is_org_page = len(relative_parts) >= 4 and relative_parts[0] == "organisations"
                if path != output_dir / "404.html" and not is_org_page:
                    warnings.append(f"Production page is noindex: {display_path(path)}")

    # Demo-specific identity disambiguation checks.
    if preview_mode:
        first = output_dir / "people" / "xx" / "a-example-001" / "index.html"
        second = output_dir / "people" / "xx" / "a-example-002" / "index.html"
        if not first.exists() or not second.exists():
            errors.append("Preview disambiguation pages are missing")
        else:
            first_text = first.read_text(encoding="utf-8")
            second_text = second.read_text(encoding="utf-8")
            if "Same published name, different identity" not in first_text:
                errors.append("Preview disambiguation notice is missing on the first same-name person")
            if "XX-2099-9999-APPT-001" not in first_text or "XX-2099-9999-APPT-002" in first_text:
                errors.append("First same-name person page merged or lost its own record")
            if "XX-2099-9999-APPT-002" not in second_text or "XX-2099-9999-APPT-001" in second_text:
                errors.append("Second same-name person page merged or lost its own record")
            if "A. E. Example" not in first_text:
                errors.append("Verified name variant is missing from the person page")
            if "A. E. Example" in second_text:
                errors.append("Verified name variant leaked to a different identity")
            tenders_page = output_dir / "tenders" / "index.html"
            if not tenders_page.exists():
                errors.append("Preview tender index is missing")
            else:
                tender_text = tenders_page.read_text(encoding="utf-8")
                for marker in ("data-tender-filters", "data-filter=\"sector\"", "data-filter=\"closing\"", "DEMO/TEND/2099/001"):
                    if marker not in tender_text:
                        errors.append(f"Preview tender filter template missing marker: {marker}")

    return errors, warnings, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Validate the designer preview")
    parser.add_argument("--dir", type=Path, help="Output directory")
    parser.add_argument("--site-url", help="Expected site origin")
    args = parser.parse_args()

    output_dir = args.dir or (ROOT / ("dist-preview" if args.preview else "dist"))
    site_url = (args.site_url or ("https://preview.invalid" if args.preview else "https://gazetteregistry.com")).rstrip("/")
    errors, warnings, report = build_validation_report(
        preview=args.preview,
        output_dir=output_dir,
        site_url=site_url,
    )

    print(f"Validated {'preview' if args.preview else 'production'} build: {display_path(output_dir)}")
    if report:
        assets = report["assets"]
        total_bytes = report["bytes"]
        largest_path, largest_bytes = report["largest_file"]
        print(f"  assets: {assets:,} files, {total_bytes / 1048576:.2f} MiB")
        print(f"  largest: {largest_path} ({largest_bytes / 1024:.1f} KiB)")
        print(
            f"  search index: {report.get('search_bytes', 0) / 1024:.1f} KiB across "
            f"{report.get('search_files', 0):,} files"
        )
        print(
            f"  html: {report.get('html', 0)} pages ({report.get('indexed_html', 0)} Pagefind bodies), "
            f"jsonld: {report.get('jsonld_blocks', 0)}, noindex pages: {report.get('noindex_pages', 0)}"
        )
        if "sitemap_urls" in report:
            print(f"  sitemap URLs: {report['sitemap_urls']}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Validation failed with {len(errors)} error(s).")
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
