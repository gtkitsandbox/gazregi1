"""Minimal XML sitemap builder with a URL-count guard."""

from __future__ import annotations

import html
from pathlib import Path

from .canonical import canonical_url


class SitemapBuilder:
    MAX_URLS = 50_000

    def __init__(self, site_url: str) -> None:
        self._site_url = site_url
        self._entries: list[tuple[str, str | None]] = []
        self._seen: set[str] = set()

    def add(self, path: str, lastmod: str | None = None) -> None:
        if path in self._seen:
            return
        self._seen.add(path)
        self._entries.append((path, lastmod))

    def write(self, output_path: Path) -> None:
        if len(self._entries) > self.MAX_URLS:
            raise ValueError(
                f"Sitemap has {len(self._entries)} URLs; split into a sitemap index above {self.MAX_URLS}."
            )
        urls = []
        for path, lastmod in self._entries:
            lastmod_xml = f"<lastmod>{html.escape(lastmod)}</lastmod>" if lastmod else ""
            urls.append(
                f"  <url><loc>{html.escape(canonical_url(path, self._site_url), quote=True)}</loc>"
                f"{lastmod_xml}</url>"
            )
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )
        output_path.write_text(content, encoding="utf-8")
