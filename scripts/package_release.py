"""Create reproducible static-deployment ZIPs and verify their contents.

The archives are written with index.html at the ZIP root, sorted entries and a
fixed timestamp so repeated packaging of the same build produces the same
archive. Generated archives stay under release/ and are not tracked by Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
ZIP_COMPRESS_LEVEL = 9

PAGES_FILE_LIMIT = 1_000
WORKERS_FILE_LIMIT = 20_000
WORKERS_FILE_BYTES = 25 * 1024 * 1024
TARGET_FILES = 15_000

FORBIDDEN_PARTS = {
    ".git",
    ".github",
    ".wrangler",
    "__pycache__",
    "chatwithcto",
    "data",
    "demo",
    "docs",
    "node_modules",
    "raw",
    "reports",
    "scripts",
    "src",
    "tests",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".env",
    ".gz",
    ".key",
    ".md",
    ".ndjson",
    ".p12",
    ".pdf",
    ".pem",
    ".pfx",
    ".py",
    ".pyc",
    ".sqlite",
}
FORBIDDEN_NAMES = {
    ".gitignore",
    "package-lock.json",
    "package.json",
    "pyrightconfig.json",
    "requirements.txt",
    "wrangler.jsonc",
    "wrangler.preview.jsonc",
}
REQUIRED_COMMON = {
    "index.html",
    "404.html",
    "robots.txt",
    "_headers",
    "assets/styles.css",
    "assets/app.js",
    "assets/favicon.svg",
    "assets/InterVariable.woff2",
    "pagefind/pagefind.js",
    "pagefind/pagefind-entry.json",
}
REQUIRED_PRODUCTION = {"sitemap.xml", "CNAME"}
REQUIRED_PREVIEW = set()


@dataclass
class PackageSpec:
    name: str
    source: Path
    zip_path: Path
    required: set[str]
    sample_paths: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files(spec: PackageSpec) -> list[Path]:
    if not spec.source.exists():
        raise SystemExit(f"{spec.source}: build output does not exist; run the build first")
    files = sorted(
        path for path in spec.source.rglob("*") if path.is_file()
    )
    problems: list[str] = []
    for path in files:
        relative = path.relative_to(spec.source)
        parts = set(relative.parts[:-1])
        if parts & FORBIDDEN_PARTS or relative.name in FORBIDDEN_NAMES:
            problems.append(f"forbidden deployment file: {relative.as_posix()}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden deployment extension: {relative.as_posix()}")
    if problems:
        raise SystemExit("\n".join(problems))
    return files


def write_archive(spec: PackageSpec, files: list[Path]) -> dict[str, object]:
    spec.zip_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = spec.zip_path.with_suffix(".zip.tmp")
    manifest_lines: list[str] = []

    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=ZIP_COMPRESS_LEVEL,
    ) as archive:
        for path in files:
            relative = path.relative_to(spec.source).as_posix()
            if relative.startswith("/") or ".." in Path(relative).parts or "\\" in relative:
                raise SystemExit(f"unsafe archive path: {relative}")
            info = zipfile.ZipInfo(relative, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
            manifest_lines.append(f"{sha256_file(path)}  {relative}")

    os.replace(temporary, spec.zip_path)

    with zipfile.ZipFile(spec.zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise SystemExit(f"{spec.zip_path}: corrupt archive entry {bad}")
        names = archive.namelist()

    if len(names) != len(files):
        raise SystemExit(f"{spec.zip_path}: expected {len(files)} entries, found {len(names)}")
    if "index.html" not in names:
        raise SystemExit(f"{spec.zip_path}: index.html is not at the archive root")
    if any(name.startswith("/") or ".." in Path(name).parts for name in names):
        raise SystemExit(f"{spec.zip_path}: archive contains an unsafe path")
    missing = sorted(spec.required - set(names))
    if missing:
        raise SystemExit(f"{spec.zip_path}: missing required files: {', '.join(missing)}")

    manifest_digest = hashlib.sha256(
        "\n".join(sorted(manifest_lines)).encode("utf-8")
    ).hexdigest()
    largest = max(files, key=lambda path: path.stat().st_size)
    uncompressed = sum(path.stat().st_size for path in files)
    archive_size = spec.zip_path.stat().st_size
    archive_digest = sha256_file(spec.zip_path)

    return {
        "zip": str(spec.zip_path.relative_to(ROOT)),
        "sha256": archive_digest,
        "size_bytes": archive_size,
        "size_mib": round(archive_size / 1048576, 3),
        "file_count": len(files),
        "uncompressed_bytes": uncompressed,
        "uncompressed_mib": round(uncompressed / 1048576, 3),
        "largest_file": {
            "path": largest.relative_to(spec.source).as_posix(),
            "bytes": largest.stat().st_size,
            "kib": round(largest.stat().st_size / 1024, 1),
        },
        "manifest_sha256": manifest_digest,
        "index_at_root": True,
        "integrity": "ok",
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def handle_error(self, _request: object, _client_address: object) -> None:
        # The verifier closes connections after reading a full response; do not
        # print expected broken-pipe tracebacks from the ephemeral test server.
        return


def fetch(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            response.read()
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def verify_standalone(spec: PackageSpec) -> dict[str, object]:
    """Extract the ZIP and serve it as an independent static site."""
    checks: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix=f"gr-{spec.name}-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(spec.zip_path) as archive:
            archive.extractall(root)
        handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
            *args, directory=str(root), **kwargs
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            base = f"http://127.0.0.1:{port}"
            for path in (
                "/",
                "/assets/styles.css",
                "/assets/app.js",
                "/assets/InterVariable.woff2",
                "/pagefind/pagefind.js",
                "/robots.txt",
                *spec.sample_paths,
            ):
                checks[path] = fetch(base + path)
            if spec.name == "production":
                checks["/sitemap.xml"] = fetch(base + "/sitemap.xml")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    failures = {path: status for path, status in checks.items() if status != 200}
    if failures:
        raise SystemExit(f"{spec.name}: standalone static check failed: {failures}")
    return {"status": "ok", "http_checks": checks}


def compatibility(file_count: int, largest_bytes: int) -> dict[str, object]:
    pages_ok = file_count <= PAGES_FILE_LIMIT
    workers_ok = file_count <= WORKERS_FILE_LIMIT and largest_bytes <= WORKERS_FILE_BYTES
    return {
        "cloudflare_pages_manual_upload": {
            "file_limit": PAGES_FILE_LIMIT,
            "compatible": pages_ok,
            "excess_files": max(0, file_count - PAGES_FILE_LIMIT),
            "note": "Pages direct upload and Cloudflare Drop share the same deployment file limit; never trim records or search shards to fit.",
        },
        "cloudflare_drop": {
            "file_limit": PAGES_FILE_LIMIT,
            "compatible": pages_ok,
            "note": "Alternative manual upload path for Pages; subject to the same limit.",
        },
        "cloudflare_workers_static_assets": {
            "file_limit": WORKERS_FILE_LIMIT,
            "per_file_limit_bytes": WORKERS_FILE_BYTES,
            "target_file_limit": TARGET_FILES,
            "compatible": workers_ok,
            "note": "Compatible with the configured Workers static-assets limits; no Worker runtime code is required.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-verify", action="store_true", help="Skip ZIP extraction and local HTTP checks")
    args = parser.parse_args()

    specs = [
        PackageSpec(
            name="production",
            source=ROOT / "dist",
            zip_path=RELEASE / "gazetteregistry-production.zip",
            required=REQUIRED_COMMON | REQUIRED_PRODUCTION,
            sample_paths=("/tenders/", "/countries/", "/about/"),
        ),
        PackageSpec(
            name="preview",
            source=ROOT / "dist-preview",
            zip_path=RELEASE / "gazetteregistry-preview.zip",
            required=REQUIRED_COMMON | REQUIRED_PREVIEW,
            sample_paths=("/tenders/", "/countries/", "/about/"),
        ),
    ]

    report: dict[str, object] = {
        "generated_by": "scripts/package_release.py",
        "deterministic": "sorted entries, fixed 1980-01-01 timestamp, stored file modes",
        "packages": {},
    }
    packages: dict[str, object] = {}
    for spec in specs:
        files = collect_files(spec)
        details = write_archive(spec, files)
        details["compatibility"] = compatibility(
            int(details["file_count"]),
            int(details["largest_file"]["bytes"]),
        )
        details["standalone"] = (
            {"status": "skipped"} if args.skip_verify else verify_standalone(spec)
        )
        packages[spec.name] = details
        print(
            f"{spec.name.capitalize()} ZIP: {details['zip']} — "
            f"{details['size_mib']} MiB, {details['file_count']:,} files, "
            f"sha256 {details['sha256']}"
        )
        print(
            f"  largest: {details['largest_file']['path']} "
            f"({details['largest_file']['kib']} KiB); "
            f"manifest sha256 {details['manifest_sha256']}"
        )
        pages = details["compatibility"]["cloudflare_pages_manual_upload"]
        workers = details["compatibility"]["cloudflare_workers_static_assets"]
        pages_status = "compatible"
        if not pages["compatible"]:
            pages_status = (
                "NOT compatible "
                f"({pages['excess_files']} files over the 1,000-file limit)"
            )
        print(f"  Cloudflare Pages manual upload: {pages_status}")
        print(
            "  Cloudflare Workers static assets: "
            f"{'compatible' if workers['compatible'] else 'NOT compatible'}"
        )
        print(f"  standalone static check: {details['standalone']['status']}")

    report["packages"] = packages
    report_path = RELEASE / "package-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {report_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
