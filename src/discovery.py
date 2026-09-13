"""
Discovery stage.

Combines two sources:

1. `data/raw/mcp_seed.py` — ~75 hand-verified, first-party vendor MCP
   servers (Stripe, Notion, GitHub, ...), each checked against the vendor's
   own documentation. Tier: `verified`.

2. `data/raw/registry_pull.json` — community MCP servers pulled live from
   Anthropic's official MCP Registry (registry.modelcontextprotocol.io) by
   `scripts/pull_registry.py`, filtered to require a real public GitHub
   repository and pass a spam/template filter. Tier:
   `community_github_verified`. This file is *generated*, not hand-authored
   — see scripts/pull_registry.py's docstring for why it has to run outside
   this sandboxed environment (no outbound network here). If it doesn't
   exist yet, discovery falls back to source (1) alone, so the pipeline
   always runs end-to-end even before anyone has run the puller.

Merging both here — rather than in extraction or later — means every
downstream stage (clean/normalize/dedupe/classify/...) sees one consistent
list of raw candidate records regardless of which source they came from.
"""
import json
import logging
from pathlib import Path

from data.raw.mcp_seed import RAW_MCP_SERVERS

logger = logging.getLogger("ingestion.discovery")

REGISTRY_PULL_PATH = Path(__file__).parent.parent / "data" / "raw" / "registry_pull.json"


def _load_registry_pull() -> list[dict]:
    if not REGISTRY_PULL_PATH.exists():
        logger.info("no registry_pull.json found — run scripts/pull_registry.py to add community servers")
        return []
    try:
        records = json.loads(REGISTRY_PULL_PATH.read_text())
        logger.info("loaded %d community records from %s", len(records), REGISTRY_PULL_PATH.name)
        return records
    except Exception as e:
        logger.warning("failed to read %s: %s — continuing with first-party seed only", REGISTRY_PULL_PATH, e)
        return []


def discover() -> list[dict]:
    """Return raw, unprocessed candidate records for the MCP Servers module,
    tagging each with its verification tier so later stages (classification,
    validation, the quality report) can report on both tiers separately."""
    first_party = [dict(r, verification_tier="verified") for r in RAW_MCP_SERVERS]
    community = _load_registry_pull()
    combined = first_party + community
    logger.info(
        "discovery total: %d records (%d verified first-party + %d community)",
        len(combined), len(first_party), len(community),
    )
    return combined
