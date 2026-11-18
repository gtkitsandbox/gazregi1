"""Per-page SEO titles, descriptions and robots directives."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageMetadata:
    title: str
    description: str
    robots: str = "index,follow"
    og_type: str = "website"


def excerpt(text: str, limit: int = 155) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def page_metadata(
    *,
    site_name: str,
    title: str,
    description: str,
    robots: str = "index,follow",
    og_type: str = "website",
) -> PageMetadata:
    full_title = title if site_name in title else f"{title} | {site_name}"
    return PageMetadata(
        title=full_title,
        description=excerpt(description),
        robots=robots,
        og_type=og_type,
    )
