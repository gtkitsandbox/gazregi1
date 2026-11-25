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
    person_id: str | None = None,
    job_titles: list[str] | None = None,
    affiliations: list[tuple[str, str]] | None = None,
    date_modified: str | None = None,
    subject_of: list[tuple[str, str, str | None]] | None = None,
) -> str:
    page_url = canonical_url(path, site_url)
    person: dict[str, Any] = {
        "@type": "Person",
        "@id": f"{page_url}#person",
        "name": person_name,
        "url": page_url,
        "mainEntityOfPage": page_url,
    }
    if person_id:
        person["identifier"] = person_id
    if alternate_names:
        person["alternateName"] = alternate_names
    if job_titles:
        person["jobTitle"] = job_titles if len(job_titles) > 1 else job_titles[0]
    if affiliations:
        person["affiliation"] = [
            {
                "@type": "Organization",
                "name": org_name,
                "url": canonical_url(org_path, site_url),
            }
            for org_name, org_path in affiliations
        ]
    if subject_of:
        person["subjectOf"] = [
            {
                "@type": "WebPage",
                "name": rec_title,
                "url": canonical_url(rec_path, site_url),
                **({"datePublished": rec_date} if rec_date else {}),
            }
            for rec_title, rec_path, rec_date in subject_of
        ]
    page: dict[str, Any] = {
        "@type": "ProfilePage",
        "@id": page_url,
        "url": page_url,
        "name": title,
        "description": description,
        "isPartOf": {"@type": "WebSite", "name": site_name, "url": canonical_url("/", site_url)},
        "mainEntity": person,
    }
    if date_modified:
        page["dateModified"] = date_modified
    keyword_bits = [person_name, *alternate_names, *(org_name for org_name, _ in (affiliations or []))]
    if keyword_bits:
        page["keywords"] = ", ".join(dict.fromkeys(keyword_bits))
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
