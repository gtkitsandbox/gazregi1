"""JSON-LD structured data builders."""

from __future__ import annotations

import json
from typing import Any

from .breadcrumbs import Crumb
from .canonical import canonical_url


def _serialise(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def breadcrumb_list(crumbs: list[Crumb], site_url: str) -> dict[str, Any]:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index + 1,
                "name": crumb.label,
                "item": canonical_url(crumb.path, site_url),
            }
            for index, crumb in enumerate(crumbs)
        ],
    }


def web_page(
    *,
    path: str,
    title: str,
    description: str,
    crumbs: list[Crumb],
    site_name: str,
    site_url: str,
    page_type: str = "WebPage",
    about: dict[str, Any] | list[dict[str, Any]] | None = None,
    citation: str | None = None,
    date_published: str | None = None,
) -> str:
    page: dict[str, Any] = {
        "@type": page_type,
        "@id": canonical_url(path, site_url),
        "url": canonical_url(path, site_url),
        "name": title,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": site_name, "url": canonical_url("/", site_url)},
    }
    if about:
        page["about"] = about
    if citation:
        page["citation"] = citation
    if date_published:
        page["datePublished"] = date_published
    graph = {"@context": "https://schema.org", "@graph": [page, breadcrumb_list(crumbs, site_url)]}
    return _serialise(graph)


def website(*, site_name: str, site_url: str, description: str) -> str:
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": canonical_url("/", site_url),
                "url": canonical_url("/", site_url),
                "name": site_name,
                "description": description,
                "inLanguage": "en",
            },
            {
                "@type": "Organization",
                "@id": f"{site_url}/#organization",
                "name": site_name,
                "url": canonical_url("/", site_url),
                "description": "Independent public-record and procurement discovery service.",
            },
        ],
    }
    return _serialise(graph)


def collection_page(
    *,
    path: str,
    title: str,
    description: str,
    crumbs: list[Crumb],
    site_name: str,
    site_url: str,
    items: list[tuple[str, str]],
) -> str:
    page = {
        "@type": "CollectionPage",
        "@id": canonical_url(path, site_url),
        "url": canonical_url(path, site_url),
        "name": title,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": site_name, "url": canonical_url("/", site_url)},
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": label,
                    "url": canonical_url(item_path, site_url),
                }
                for index, (label, item_path) in enumerate(items)
            ],
        },
    }
    graph = {"@context": "https://schema.org", "@graph": [page, breadcrumb_list(crumbs, site_url)]}
    return _serialise(graph)


def profile_page(
    *,
    path: str,
    title: str,
    description: str,
    crumbs: list[Crumb],
    site_name: str,
    site_url: str,
    person_name: str,
    alternate_names: list[str],
) -> str:
    person: dict[str, Any] = {
        "@type": "Person",
        "name": person_name,
        "url": canonical_url(path, site_url),
    }
    if alternate_names:
        person["alternateName"] = alternate_names
    page = {
        "@type": "ProfilePage",
        "@id": canonical_url(path, site_url),
        "url": canonical_url(path, site_url),
        "name": title,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": site_name, "url": canonical_url("/", site_url)},
        "mainEntity": person,
    }
    graph = {"@context": "https://schema.org", "@graph": [page, breadcrumb_list(crumbs, site_url)]}
    return _serialise(graph)


def organisation_page(
    *,
    path: str,
    title: str,
    description: str,
    crumbs: list[Crumb],
    site_name: str,
    site_url: str,
    organisation_name: str,
    alternate_names: list[str],
) -> str:
    organisation: dict[str, Any] = {
        "@type": "Organization",
        "name": organisation_name,
        "url": canonical_url(path, site_url),
    }
    if alternate_names:
        organisation["alternateName"] = alternate_names
    page = {
        "@type": "AboutPage",
        "@id": canonical_url(path, site_url),
        "url": canonical_url(path, site_url),
        "name": title,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": site_name, "url": canonical_url("/", site_url)},
        "mainEntity": organisation,
    }
    graph = {"@context": "https://schema.org", "@graph": [page, breadcrumb_list(crumbs, site_url)]}
    return _serialise(graph)
