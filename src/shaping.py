"""Shape internal working records into the project's Common Entity Schema,
adding the MCP-specific metadata block required by the spec (installation
method + runtime requirements)."""
from src.schema import stable_uuid, official_logo_url


def shape_mcp_record(rec: dict) -> dict:
    entity_id = stable_uuid("mcp", rec["name"], rec["vendor_domain"])
    return {
        "id": entity_id,
        "entity_type": "mcp",
        "name": rec["name"],
        "description": rec["description"],
        "url": rec["docs_url"],
        "logo_url": official_logo_url(rec["vendor_domain"]),
        "categories": rec["categories"],
        "source": {"name": rec["source_name"], "url": rec["source_url"]},
        "metadata": {
            "vendor": rec["vendor"],
            "server_url": rec["server_url"],
            "auth_type": rec["auth_type"],
            "transport": rec["transport"],
            "installation": rec["runtime"],
            "runtime_requirements": rec["runtime"],
        },
    }


def shape(records: list[dict]) -> list[dict]:
    return [shape_mcp_record(r) for r in records]
