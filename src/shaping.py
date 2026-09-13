"""Shape internal working records into the project's Common Entity Schema,
adding the MCP-specific metadata block required by the spec (installation
method + runtime requirements)."""
from src.schema import stable_uuid, official_logo_url, github_avatar_url


def _resolve_logo(rec: dict) -> str:
    if rec["vendor_domain"] == "github.com" and rec.get("repo_owner"):
        return github_avatar_url(rec["repo_owner"])
    return official_logo_url(rec["vendor_domain"])


def shape_mcp_record(rec: dict) -> dict:
    entity_id = stable_uuid("mcp", rec["name"], rec.get("repo_url") or rec["vendor_domain"])
    metadata = {
        "vendor": rec["vendor"],
        "server_url": rec["server_url"],
        "auth_type": rec["auth_type"],
        "transport": rec["transport"],
        "installation": rec["runtime"],
        "runtime_requirements": rec["runtime"],
    }
    # Repository enrichment (spec's "Repositories: stars, primary language,
    # last updated" fields) is only present for community-tier records
    # pulled via scripts/pull_registry.py --enrich-github.
    if rec.get("repo_url"):
        metadata["repository"] = {
            "url": rec["repo_url"],
            "stars": rec.get("stars"),
            "primary_language": rec.get("primary_language"),
            "last_updated": rec.get("last_updated"),
        }
    return {
        "id": entity_id,
        "entity_type": "mcp",
        "name": rec["name"],
        "description": rec["description"],
        "url": rec["docs_url"],
        "logo_url": _resolve_logo(rec),
        "categories": rec["categories"],
        "source": {"name": rec["source_name"], "url": rec["source_url"]},
        "verification_status": rec.get("verification_tier", "verified"),
        "description_source": rec.get("description_source", "llm_curated"),
        "metadata": metadata,
    }


def shape(records: list[dict]) -> list[dict]:
    return [shape_mcp_record(r) for r in records]
