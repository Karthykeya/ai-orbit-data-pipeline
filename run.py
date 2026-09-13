#!/usr/bin/env python3
"""AI Orbit Data Ingestion Pipeline — entry point.

Workflow: Discovery -> Extraction -> Cleaning -> Normalization ->
          Deduplication -> Classification -> Description Generation ->
          Shaping -> Relationship Mapping -> Validation -> Write outputs

Run:  python run.py
Output: data/mcp_servers.json, data/companies.json, data/relationships.json
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src import discovery, extraction, cleaning, normalization, deduplication
from src import classification, descriptions, shaping, relationships, validation

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingestion.run")

OUT_DIR = Path(__file__).parent / "data"


def main() -> None:
    logger.info("=== Stage 1/8: Discovery ===")
    raw = discovery.discover()
    logger.info("discovered %d raw candidate records", len(raw))

    logger.info("=== Stage 2/8: Extraction ===")
    records = extraction.extract(raw)

    logger.info("=== Stage 3/8: Cleaning ===")
    records = cleaning.clean(records)

    logger.info("=== Stage 4/8: Normalization (entity resolution) ===")
    records = normalization.normalize(records)
    fuzzy = normalization.find_fuzzy_candidates([r["vendor"] for r in records])
    if fuzzy:
        logger.info("fuzzy vendor-name candidates for manual review: %s", fuzzy)

    logger.info("=== Stage 5/8: Deduplication ===")
    records = deduplication.dedupe(records)

    logger.info("=== Stage 6/8: Classification ===")
    records = classification.classify(records)

    logger.info("=== Stage 7/8: Description Generation (LLM) ===")
    records = descriptions.generate(records)

    logger.info("=== Stage 8/8: Shaping, Relationships, Validation ===")
    shaped = shaping.shape(records)
    shaped = validation.validate(shaped)

    company_records = relationships.build_company_records(records)
    repository_records = relationships.build_repository_records(records)
    rel_records = relationships.build_relationships(shaped, company_records, repository_records)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mcp_servers.json").write_text(json.dumps(shaped, indent=2))
    (OUT_DIR / "companies.json").write_text(json.dumps(company_records, indent=2))
    (OUT_DIR / "repositories.json").write_text(json.dumps(repository_records, indent=2))
    (OUT_DIR / "relationships.json").write_text(json.dumps(rel_records, indent=2))

    logger.info(
        "Done. Wrote %d MCP records (%d verified / %d community), %d companies, %d repositories, %d relationships to %s",
        len(shaped),
        sum(1 for r in shaped if r["verification_status"] == "verified"),
        sum(1 for r in shaped if r["verification_status"] != "verified"),
        len(company_records), len(repository_records), len(rel_records), OUT_DIR,
    )


if __name__ == "__main__":
    main()
