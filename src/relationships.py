"""Relationship-mapping stage.

Produces relationships.json capturing the ecosystem web named in the spec.
For the MCP module, the primary edge is:

    Company --develops--> MCP Server
    MCP Server --integrates_with--> Tool   (the vendor's own core product)

Each MCP server is, by construction, built by the same company whose
platform it integrates with, so both edges can be derived directly from the
cleaned record without extra lookups — this is the "sophisticated
relationship density" the spec calls for despite a single source module.
"""
from src.schema import stable_uuid


def build_company_records(mcp_records: list[dict]) -> list[dict]:
    companies = {}
    for rec in mcp_records:
        vendor = rec["vendor"]
        if vendor in companies:
            continue
        companies[vendor] = {
            "id": stable_uuid("company", vendor),
            "entity_type": "company",
            "name": vendor,
            "description": f"Maintainer of {rec['name']} and related products on {rec['vendor_domain']}.",
            "url": f"https://{rec['vendor_domain']}",
            "categories": ["Company"],
            "source": {"name": rec["source_name"], "url": rec["source_url"]},
            "headquarters": None,
            "founding_year": None,
            "industry_sector": "AI / Developer Tools" if "Dev Tools" in rec["categories"] else "Software",
        }
    return list(companies.values())


def build_relationships(shaped_mcp_records: list[dict], company_records: list[dict]) -> list[dict]:
    """`shaped_mcp_records` are already in Common Entity Schema form (id, name,
    metadata.vendor, ...) — this runs *after* shaping.shape()."""
    company_id_by_name = {c["name"]: c["id"] for c in company_records}
    rels = []
    for rec in shaped_mcp_records:
        vendor = rec["metadata"]["vendor"]
        company_id = company_id_by_name.get(vendor)
        if not company_id:
            continue
        rels.append({
            "id": stable_uuid("rel", "develops", company_id, rec["id"]),
            "type": "develops",
            "source_id": company_id,
            "source_type": "company",
            "target_id": rec["id"],
            "target_type": "mcp",
        })
        rels.append({
            "id": stable_uuid("rel", "integrates_with", rec["id"], company_id),
            "type": "integrates_with",
            "source_id": rec["id"],
            "source_type": "mcp",
            "target_id": company_id,
            "target_type": "tool",
            "note": f"{rec['name']} integrates with {vendor}'s own platform/API.",
        })
    return rels
