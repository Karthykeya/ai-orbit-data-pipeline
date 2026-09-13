#!/usr/bin/env python3
"""Generate data/quality_report.json — automated, re-computable metrics on
the final dataset, so quality claims in the README are backed by a number
anyone can regenerate by running this script, not just asserted in prose.

Run after run.py:
    python scripts/quality_report.py
"""
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"


def pct(n: int, total: int) -> float:
    return round(100 * n / total, 2) if total else 0.0


def is_official_looking(url: str, source_url: str) -> bool:
    """True if the record's public URL and its verification source URL
    share the same host — i.e. we're not pointing at one domain while our
    verification note points at another."""
    try:
        return urlsplit(url).netloc == urlsplit(source_url).netloc
    except Exception:
        return False


def community_url_matches_repo(rec: dict) -> bool:
    """For community records, `source.url` is deliberately a different host
    (the MCP Registry, where the record was discovered) than `url` (the
    entity's own GitHub repo) — that's correct, not a traceability gap. The
    real check for this tier is: does `url` match the repo we say backs it?"""
    repo_url = rec.get("metadata", {}).get("repository", {}).get("url", "")
    return bool(repo_url) and rec.get("url", "") == repo_url


def main() -> None:
    mcp = json.loads((DATA / "mcp_servers.json").read_text())
    companies = json.loads((DATA / "companies.json").read_text())
    repositories_path = DATA / "repositories.json"
    repositories = json.loads(repositories_path.read_text()) if repositories_path.exists() else []
    rels = json.loads((DATA / "relationships.json").read_text())

    total = len(mcp)
    verified = [r for r in mcp if r["verification_status"] == "verified"]
    community = [r for r in mcp if r["verification_status"] != "verified"]
    ids = [r["id"] for r in mcp]
    names_domains = [(r["name"].strip().lower(), r["metadata"]["vendor"].strip().lower()) for r in mcp]

    duplicate_ids = total - len(set(ids))
    duplicate_name_vendor_pairs = total - len(set(names_domains))

    has_description = sum(1 for r in mcp if len(r.get("description", "")) >= 20)
    has_official_url = sum(1 for r in mcp if r.get("url", "").startswith("http"))
    has_logo = sum(1 for r in mcp if r.get("logo_url", "").startswith("http"))
    url_matches_source_host = sum(
        1 for r in verified if is_official_looking(r["url"], r["source"]["url"])
    )
    community_url_matches_repo_count = sum(1 for r in community if community_url_matches_repo(r))

    description_source_counts = Counter(r.get("description_source", "unknown") for r in mcp)
    category_counts = Counter(c for r in mcp for c in r["categories"])
    transport_counts = Counter(r["metadata"]["transport"] for r in mcp)
    auth_counts = Counter(r["metadata"]["auth_type"] for r in mcp)

    companies_with_hq = sum(1 for c in companies if c.get("headquarters"))
    companies_with_year = sum(1 for c in companies if c.get("founding_year"))
    repos_with_stars = sum(1 for r in repositories if r.get("stars") is not None)

    rel_types = Counter(r["type"] for r in rels)

    report = {
        "generated_by": "scripts/quality_report.py",
        "dataset": "MCP Servers module",
        "totals": {
            "mcp_records": total,
            "verified_first_party_records": len(verified),
            "community_github_verified_records": len(community),
            "company_records": len(companies),
            "repository_records": len(repositories),
            "relationship_records": len(rels),
        },
        "integrity": {
            "duplicate_ids": duplicate_ids,
            "duplicate_name_vendor_pairs": duplicate_name_vendor_pairs,
            "passes_uniqueness_check": duplicate_ids == 0 and duplicate_name_vendor_pairs == 0,
        },
        "completeness": {
            "description_coverage_pct": pct(has_description, total),
            "official_url_coverage_pct": pct(has_official_url, total),
            "logo_url_coverage_pct": pct(has_logo, total),
        },
        "description_sourcing": dict(description_source_counts.most_common()),
        "traceability": {
            "verified_tier_url_and_source_same_host_pct": pct(url_matches_source_host, len(verified)) if verified else None,
            "community_tier_url_matches_declared_repo_pct": pct(community_url_matches_repo_count, len(community)) if community else None,
            "note": "Verified-tier records point `url` and `source.url` at the same vendor host. Community-tier records legitimately have a different source host (the MCP Registry) — for that tier we instead check `url` matches the declared repository URL.",
        },
        "company_enrichment": {
            "companies_with_headquarters_pct": pct(companies_with_hq, len(companies)) if companies else None,
            "companies_with_founding_year_pct": pct(companies_with_year, len(companies)) if companies else None,
        },
        "repository_enrichment": {
            "repositories_with_github_stars_pct": pct(repos_with_stars, len(repositories)) if repositories else None,
            "note": "Populated when scripts/pull_registry.py was run with --enrich-github; null fields are honestly reported, never guessed.",
        },
        "distribution": {
            "by_category": dict(category_counts.most_common()),
            "by_transport": dict(transport_counts.most_common()),
            "by_auth_type": dict(auth_counts.most_common()),
            "by_relationship_type": dict(rel_types.most_common()),
        },
    }

    out_path = DATA / "quality_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    if not report["integrity"]["passes_uniqueness_check"]:
        print("QUALITY GATE FAILED: duplicate records detected", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
