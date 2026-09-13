"""Classification stage: assign entity_type and finalize category tags."""

ENTITY_TYPE = "mcp"


def classify(records: list[dict]) -> list[dict]:
    out = []
    for rec in records:
        rec = dict(rec)
        rec["entity_type"] = ENTITY_TYPE
        categories = set(rec.get("categories", []))
        categories.add("MCP")
        rec["categories"] = sorted(categories)
        out.append(rec)
    return out
