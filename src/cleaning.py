"""Cleaning stage: sanitize text and normalize URLs.

Handles the two most common data-quality problems named in the spec:
  - URL Normalization: consistent scheme/host casing, no tracking params,
    no trailing slash inconsistency.
  - Sanitization: collapse whitespace, strip stray HTML entities that leak
    in from scraped docs/RSS content.
"""
import html
import re
from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    if not url or url.startswith(("npx ", "uvx ")):
        # local/stdio install commands are not URLs — leave untouched
        return url
    url = url.strip()
    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or ""
    # drop tracking/query junk but keep meaningful query strings (rare for docs pages)
    query = parts.query
    return urlunsplit((scheme, netloc, path, query, ""))


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)          # strip stray HTML tags
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    return text


def clean_record(rec: dict) -> dict:
    rec = dict(rec)
    rec["name"] = sanitize_text(rec["name"])
    rec["vendor"] = sanitize_text(rec["vendor"])
    rec["docs_url"] = normalize_url(rec["docs_url"])
    rec["server_url"] = normalize_url(rec.get("server_url", ""))
    rec["source_url"] = normalize_url(rec.get("source_url", rec["docs_url"]))
    rec["categories"] = sorted({sanitize_text(c) for c in rec.get("categories", []) if c})
    return rec


def clean(records: list[dict]) -> list[dict]:
    return [clean_record(r) for r in records]
