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

# Manually verified company metadata (headquarters, founding year, industry
# sector) for the required "Specialized Metadata" fields on Company records.
# Sourced from each company's own About/Newsroom page — kept separate from
# the MCP seed data since it describes the *vendor*, not the server, and is
# reused across every MCP server that vendor publishes.
COMPANY_FACTS = {
    "GitHub": {"headquarters": "San Francisco, California, USA", "founding_year": 2008, "industry_sector": "Developer Tools / Version Control"},
    "Notion": {"headquarters": "San Francisco, California, USA", "founding_year": 2013, "industry_sector": "Productivity Software"},
    "Stripe": {"headquarters": "South San Francisco, California, USA", "founding_year": 2010, "industry_sector": "Financial Technology / Payments"},
    "Linear": {"headquarters": "San Francisco, California, USA", "founding_year": 2019, "industry_sector": "Developer Tools / Project Management"},
    "Slack": {"headquarters": "San Francisco, California, USA", "founding_year": 2013, "industry_sector": "Business Communication"},
    "Atlassian": {"headquarters": "Sydney, Australia", "founding_year": 2002, "industry_sector": "Developer Tools / Collaboration Software"},
    "HubSpot": {"headquarters": "Cambridge, Massachusetts, USA", "founding_year": 2006, "industry_sector": "Marketing & Sales Software (CRM)"},
    "Supabase": {"headquarters": "San Francisco, California, USA", "founding_year": 2020, "industry_sector": "Backend-as-a-Service / Database"},
    "Cloudflare": {"headquarters": "San Francisco, California, USA", "founding_year": 2009, "industry_sector": "Cloud / Network Infrastructure"},
    "Vercel": {"headquarters": "San Francisco, California, USA", "founding_year": 2015, "industry_sector": "Cloud / Frontend Deployment"},
    "Sentry": {"headquarters": "San Francisco, California, USA", "founding_year": 2012, "industry_sector": "Developer Tools / Observability"},
    "PayPal": {"headquarters": "San Jose, California, USA", "founding_year": 1998, "industry_sector": "Financial Technology / Payments"},
    "Asana": {"headquarters": "San Francisco, California, USA", "founding_year": 2008, "industry_sector": "Productivity / Project Management"},
    "ClickUp": {"headquarters": "San Diego, California, USA", "founding_year": 2017, "industry_sector": "Productivity / Project Management"},
    "monday.com": {"headquarters": "Tel Aviv, Israel", "founding_year": 2012, "industry_sector": "Work Management Software"},
    "Miro": {"headquarters": "San Francisco, California, USA", "founding_year": 2011, "industry_sector": "Visual Collaboration Software"},
    "Intercom": {"headquarters": "San Francisco, California, USA", "founding_year": 2011, "industry_sector": "Customer Messaging / Support"},
    "PagerDuty": {"headquarters": "San Francisco, California, USA", "founding_year": 2009, "industry_sector": "Developer Tools / Incident Response"},
    "Neon": {"headquarters": "San Francisco, California, USA", "founding_year": 2021, "industry_sector": "Database / Serverless Postgres"},
    "Netlify": {"headquarters": "San Francisco, California, USA", "founding_year": 2014, "industry_sector": "Cloud / Web Deployment"},
    "Prisma": {"headquarters": "Berlin, Germany", "founding_year": 2016, "industry_sector": "Database Tooling"},
    "Render": {"headquarters": "San Francisco, California, USA", "founding_year": 2018, "industry_sector": "Cloud Hosting"},
    "Replicate": {"headquarters": "San Francisco, California, USA", "founding_year": 2019, "industry_sector": "AI Model Hosting"},
    "Sanity": {"headquarters": "San Francisco, California, USA", "founding_year": 2015, "industry_sector": "Headless CMS"},
    "Semgrep": {"headquarters": "San Francisco, California, USA", "founding_year": 2016, "industry_sector": "Application Security"},
    "Square": {"headquarters": "San Francisco, California, USA", "founding_year": 2009, "industry_sector": "Financial Technology / Payments"},
    "Stack Overflow": {"headquarters": "New York City, New York, USA", "founding_year": 2008, "industry_sector": "Developer Q&A / Knowledge Base"},
    "Typeform": {"headquarters": "Barcelona, Spain", "founding_year": 2012, "industry_sector": "Online Forms & Surveys"},
    "Stytch": {"headquarters": "San Francisco, California, USA", "founding_year": 2020, "industry_sector": "Authentication / Identity"},
    "Zapier": {"headquarters": "Sunnyvale, California, USA", "founding_year": 2011, "industry_sector": "Workflow Automation"},
    "Wix": {"headquarters": "Tel Aviv, Israel", "founding_year": 2006, "industry_sector": "Website Builder / Cloud"},
    "Postman": {"headquarters": "San Francisco, California, USA", "founding_year": 2014, "industry_sector": "API Development Tools"},
    "PostHog": {"headquarters": "San Francisco, California, USA", "founding_year": 2020, "industry_sector": "Product Analytics"},
    "Pipedrive": {"headquarters": "Tallinn, Estonia / New York, USA", "founding_year": 2010, "industry_sector": "Sales CRM"},
    "Pipedream": {"headquarters": "San Francisco, California, USA", "founding_year": 2015, "industry_sector": "Workflow Automation / iPaaS"},
    "Plaid": {"headquarters": "San Francisco, California, USA", "founding_year": 2013, "industry_sector": "Financial Technology / Banking APIs"},
    "Ramp": {"headquarters": "New York City, New York, USA", "founding_year": 2019, "industry_sector": "Corporate Finance / Spend Management"},
    "Coda": {"headquarters": "San Francisco, California, USA", "founding_year": 2014, "industry_sector": "Productivity / Docs"},
    "Cloudinary": {"headquarters": "Santa Clara, California, USA", "founding_year": 2012, "industry_sector": "Media Management / Cloud"},
    "Upstash (Context7)": {"headquarters": "San Francisco, California, USA", "founding_year": 2021, "industry_sector": "Developer Tools / Documentation Retrieval"},
    "Attio": {"headquarters": "London, United Kingdom", "founding_year": 2019, "industry_sector": "CRM Software"},
    "Close": {"headquarters": "San Francisco, California, USA", "founding_year": 2013, "industry_sector": "Sales CRM"},
    "Ashby": {"headquarters": "San Francisco, California, USA", "founding_year": 2018, "industry_sector": "Recruiting Software (ATS)"},
    "Buildkite": {"headquarters": "Melbourne, Australia", "founding_year": 2013, "industry_sector": "CI/CD Infrastructure"},
    "Canva": {"headquarters": "Sydney, Australia", "founding_year": 2012, "industry_sector": "Design Software"},
    "Apify": {"headquarters": "Prague, Czech Republic", "founding_year": 2015, "industry_sector": "Web Scraping / Automation"},
    "Amplitude": {"headquarters": "San Francisco, California, USA", "founding_year": 2012, "industry_sector": "Product Analytics"},
    "Astro": {"headquarters": "Remote / New York, USA", "founding_year": 2021, "industry_sector": "Web Framework"},
    "Braintrust": {"headquarters": "San Francisco, California, USA", "founding_year": 2023, "industry_sector": "LLM Evaluation Tooling"},
    "Browser Use": {"headquarters": "San Francisco, California, USA", "founding_year": 2024, "industry_sector": "AI Browser Automation"},
    "Devin AI (Cognition)": {"headquarters": "San Francisco, California, USA", "founding_year": 2023, "industry_sector": "AI Coding Agents"},
    "draw.io (JGraph)": {"headquarters": "London, United Kingdom", "founding_year": 2005, "industry_sector": "Diagramming Software"},
    "Excalidraw": {"headquarters": "Remote", "founding_year": 2020, "industry_sector": "Diagramming / Whiteboarding"},
    "Fireflies.ai": {"headquarters": "San Francisco, California, USA", "founding_year": 2016, "industry_sector": "Meeting Intelligence / AI Notetaking"},
    "Google": {"headquarters": "Mountain View, California, USA", "founding_year": 1998, "industry_sector": "Internet Services / Cloud"},
    "Honeycomb": {"headquarters": "San Francisco, California, USA", "founding_year": 2016, "industry_sector": "Observability"},
    "Hugging Face": {"headquarters": "New York City, New York, USA", "founding_year": 2016, "industry_sector": "AI Models / Open-Source ML"},
    "Instant": {"headquarters": "San Francisco, California, USA", "founding_year": 2022, "industry_sector": "Realtime Database"},
    "Jamie": {"headquarters": "Berlin, Germany", "founding_year": 2023, "industry_sector": "AI Meeting Assistant"},
    "Leadfeeder": {"headquarters": "Helsinki, Finland", "founding_year": 2012, "industry_sector": "Sales Intelligence / Lead Generation"},
    "Microsoft": {"headquarters": "Redmond, Washington, USA", "founding_year": 1975, "industry_sector": "Software / Cloud"},
    "Mobbin": {"headquarters": "Singapore", "founding_year": 2019, "industry_sector": "Design Reference Library"},
    "Modjo": {"headquarters": "Paris, France", "founding_year": 2020, "industry_sector": "Conversation Intelligence"},
    "Pennylane": {"headquarters": "Paris, France", "founding_year": 2020, "industry_sector": "Accounting Software"},
    "Spendesk": {"headquarters": "Paris, France", "founding_year": 2016, "industry_sector": "Spend Management"},
    "Statista": {"headquarters": "Hamburg, Germany", "founding_year": 2007, "industry_sector": "Market & Consumer Data"},
    "Supercut": {"headquarters": "San Francisco, California, USA", "founding_year": 2023, "industry_sector": "Video Intelligence"},
    "Superglue": {"headquarters": "San Francisco, California, USA", "founding_year": 2024, "industry_sector": "API Integration Automation"},
    "Anthropic / MCP Steering Group": {"headquarters": "San Francisco, California, USA", "founding_year": 2021, "industry_sector": "AI Research / Foundation Models"},
}


def build_company_records(mcp_records: list[dict]) -> list[dict]:
    """Company entities are only derived for the first-party (`verified`)
    tier, where `vendor` is genuinely a company. For community records,
    `vendor` is a GitHub username/org — building a "Company" entity for an
    individual maintainer would misuse the schema, so those get a
    Repository entity instead (see `build_repository_records`)."""
    companies = {}
    for rec in mcp_records:
        if rec.get("verification_tier", "verified") != "verified":
            continue
        vendor = rec["vendor"]
        if vendor in companies:
            continue
        facts = COMPANY_FACTS.get(vendor, {})
        companies[vendor] = {
            "id": stable_uuid("company", vendor),
            "entity_type": "company",
            "name": vendor,
            "description": f"Maintainer of {rec['name']} and related products on {rec['vendor_domain']}.",
            "url": f"https://{rec['vendor_domain']}",
            "categories": ["Company"],
            "source": {"name": rec["source_name"], "url": rec["source_url"]},
            "headquarters": facts.get("headquarters"),
            "founding_year": facts.get("founding_year"),
            "industry_sector": facts.get("industry_sector", "Software"),
        }
    return list(companies.values())


def build_repository_records(mcp_records: list[dict]) -> list[dict]:
    """Repository entities for the community tier — this is the spec's
    'Repositories: GitHub/open-source projects' category, populated as a
    natural side-effect of the same MCP source data rather than a separate
    crawl, with the exact 'stars, primary language, last updated' fields
    the spec asks for (populated when `pull_registry.py --enrich-github`
    was used; null otherwise, never guessed)."""
    repos = {}
    for rec in mcp_records:
        if rec.get("verification_tier", "verified") == "verified":
            continue
        repo_url = rec.get("repo_url")
        if not repo_url or repo_url in repos:
            continue
        repos[repo_url] = {
            "id": stable_uuid("repository", repo_url),
            "entity_type": "repository",
            "name": rec.get("repo_name") or rec["name"],
            "description": f"GitHub repository publishing the {rec['name']} MCP server.",
            "url": repo_url,
            "categories": ["Repository", "MCP"],
            "source": {"name": rec["source_name"], "url": rec["source_url"]},
            "owner": rec.get("repo_owner"),
            "stars": rec.get("stars"),
            "primary_language": rec.get("primary_language"),
            "last_updated": rec.get("last_updated"),
        }
    return list(repos.values())


def build_relationships(shaped_mcp_records: list[dict], company_records: list[dict],
                         repository_records: list[dict] | None = None) -> list[dict]:
    """`shaped_mcp_records` are already in Common Entity Schema form (id, name,
    metadata.vendor, ...) — this runs *after* shaping.shape()."""
    repository_records = repository_records or []
    company_id_by_name = {c["name"]: c["id"] for c in company_records}
    repo_id_by_url = {r["url"]: r["id"] for r in repository_records}
    rels = []
    for rec in shaped_mcp_records:
        if rec.get("verification_status") == "verified":
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
        else:
            repo_url = rec["metadata"].get("repository", {}).get("url")
            repo_id = repo_id_by_url.get(repo_url)
            if not repo_id:
                continue
            rels.append({
                "id": stable_uuid("rel", "hosted_in", rec["id"], repo_id),
                "type": "hosted_in",
                "source_id": rec["id"],
                "source_type": "mcp",
                "target_id": repo_id,
                "target_type": "repository",
            })
    return rels
