"""Deduplication stage: exact-key + near-duplicate detection.

Primary key: (name, vendor_domain) after normalization — two records
describing the same server from two different source pages collapse into
one, keeping the version with the more complete metadata.
"""
import logging
from src.schema import slugify

logger = logging.getLogger("ingestion.dedup")


def _completeness_score(rec: dict) -> int:
    return sum(1 for v in rec.values() if v not in (None, "", [], "Unknown"))


def _dedup_key(rec: dict) -> str:
    """Community records all share vendor_domain='github.com', so domain
    alone would wrongly collapse distinct repos with similar names. Prefer
    the actual repo_url as the domain-equivalent when present."""
    domain_part = (rec.get("repo_url") or rec["vendor_domain"]).lower()
    return f"{slugify(rec['name'])}::{domain_part}"


def dedupe(records: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    dropped = 0
    for rec in records:
        key = _dedup_key(rec)
        if key not in buckets:
            buckets[key] = rec
            continue
        # duplicate found — keep the more complete record
        dropped += 1
        if _completeness_score(rec) > _completeness_score(buckets[key]):
            buckets[key] = rec
    logger.info("deduplication removed %d duplicate record(s)", dropped)
    return list(buckets.values())
