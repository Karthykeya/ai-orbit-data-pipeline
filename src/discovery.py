"""
Discovery stage.

In production this stage would call each source's API:
  - GitHub Search/Repos API for modelcontextprotocol/servers + org repos
  - Vendor developer-docs sitemaps (developers.notion.com, docs.stripe.com, ...)
  - The MCP Registry API (https://registry.modelcontextprotocol.io) once GA

This sandboxed environment has no outbound network access, so discovery was
performed manually through the same APIs/docs a script would hit, and the
verified results were captured as the structured seed in `data/raw/mcp_seed.py`
(see the `source_url` field on every record for the exact page checked).
`discover()` is written so that swapping in real HTTP calls later requires no
change to the rest of the pipeline — it only needs to keep returning a list of
raw dicts shaped like the seed records.
"""
from data.raw.mcp_seed import RAW_MCP_SERVERS


def discover() -> list[dict]:
    """Return raw, unprocessed candidate records for the MCP Servers module."""
    return list(RAW_MCP_SERVERS)
