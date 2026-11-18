"""Reusable ingestion framework for official international sources.

Adapters fetch official records, normalise them into document snapshots and
curated-record drafts, and write the same NDJSON files the static build reads.
No adapter writes HTML; the build layer owns all presentation.
"""
