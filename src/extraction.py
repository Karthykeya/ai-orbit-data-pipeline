"""Extraction stage: pull the fields we care about out of each raw source
record and coerce them into a consistent working shape. Missing fields are
logged and defaulted rather than raising, per the resilience requirement."""
import logging

logger = logging.getLogger("ingestion.extraction")

REQUIRED_FIELDS = ["name", "vendor", "docs_url", "vendor_domain"]


def extract(raw_records: list[dict]) -> list[dict]:
    extracted = []
    for i, rec in enumerate(raw_records):
        missing = [f for f in REQUIRED_FIELDS if not rec.get(f)]
        if missing:
            logger.warning("record %d missing required fields %s — skipping", i, missing)
            continue
        extracted.append({
            "name": rec["name"].strip(),
            "vendor": rec["vendor"].strip(),
            "docs_url": rec["docs_url"].strip(),
            "server_url": rec.get("server_url", "").strip(),
            "vendor_domain": rec["vendor_domain"].strip(),
            "auth_type": rec.get("auth_type", "Unknown"),
            "transport": rec.get("transport", "Unknown"),
            "categories": rec.get("categories", []),
            "runtime": rec.get("runtime", "Unknown"),
            "source_name": rec.get("source_name", rec["vendor"]),
            "source_url": rec.get("source_url", rec["docs_url"]),
        })
    logger.info("extracted %d/%d records", len(extracted), len(raw_records))
    return extracted
