"""Canonical URL helpers for the static build."""

from __future__ import annotations

import os

# Override with SITE_URL or the build --site-url flag before deploying.
DEFAULT_SITE_URL = "https://gazetteregistry.com"


def site_base_url() -> str:
    return os.environ.get("SITE_URL", DEFAULT_SITE_URL).rstrip("/")


def canonical_url(path: str, base_url: str | None = None) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{(base_url or site_base_url()).rstrip('/')}{path}"
