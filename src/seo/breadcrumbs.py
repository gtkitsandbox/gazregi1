"""Breadcrumb trails shared between page templates and structured data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Crumb:
    label: str
    path: str


def crumbs(*items: tuple[str, str]) -> list[Crumb]:
    return [Crumb(label=label, path=path) for label, path in items]
