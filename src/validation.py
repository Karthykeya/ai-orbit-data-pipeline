"""Validation stage: final integrity checks before writing outputs.
Raises on hard failures (missing id/name/url); logs+drops on soft failures."""
import logging
from urllib.parse import urlsplit

logger = logging.getLogger("ingestion.validation")

REQUIRED = ["id", "entity_type", "name", "description", "url", "categories", "source"]


def _valid_url(url: str) -> bool:
    if url.startswith(("npx ", "uvx ")):
        return True  # local install commands are valid "urls" for local servers
    parts = urlsplit(url)
    return bool(parts.scheme in ("http", "https") and parts.netloc)


def validate(records: list[dict]) -> list[dict]:
    valid, seen_ids = [], set()
    for rec in records:
        missing = [f for f in REQUIRED if rec.get(f) in (None, "", [])]
        if missing:
            logger.warning("dropping %s — missing %s", rec.get("name", "<unknown>"), missing)
            continue
        if rec["id"] in seen_ids:
            logger.warning("dropping %s — duplicate id after dedup", rec["name"])
            continue
        if not _valid_url(rec["url"]):
            logger.warning("dropping %s — invalid url %r", rec["name"], rec["url"])
            continue
        seen_ids.add(rec["id"])
        valid.append(rec)
    logger.info("validation passed %d/%d records", len(valid), len(records))
    return valid
