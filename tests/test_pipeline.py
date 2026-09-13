"""Unit tests for the AI Orbit ingestion pipeline.

Run with:  pytest -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src import cleaning, normalization, deduplication, validation, classification, shaping, descriptions
from src.schema import stable_uuid, slugify, apex_domain, official_logo_url


# ---------- schema.py ----------

def test_stable_uuid_is_deterministic():
    a = stable_uuid("mcp", "Notion MCP Server", "notion.com")
    b = stable_uuid("mcp", "Notion MCP Server", "notion.com")
    assert a == b


def test_stable_uuid_is_case_and_whitespace_insensitive():
    a = stable_uuid("mcp", "Notion MCP Server", "notion.com")
    b = stable_uuid("mcp", "  NOTION mcp server  ", "NOTION.COM")
    assert a == b


def test_stable_uuid_differs_for_different_inputs():
    a = stable_uuid("mcp", "Notion MCP Server", "notion.com")
    b = stable_uuid("mcp", "Slack MCP Server", "slack.com")
    assert a != b


def test_slugify_basic():
    assert slugify("GitHub MCP Server!") == "github-mcp-server"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_apex_domain_strips_scheme_and_www():
    assert apex_domain("https://www.notion.com/path") == "notion.com"
    assert apex_domain("HTTP://Stripe.com") == "stripe.com"


def test_official_logo_url_uses_apex_domain():
    assert official_logo_url("https://www.example.com") == "https://logo.clearbit.com/example.com"


# ---------- cleaning.py ----------

def test_normalize_url_lowercases_host_and_strips_trailing_slash():
    assert cleaning.normalize_url("https://Example.COM/path/") == "https://example.com/path"


def test_normalize_url_preserves_local_install_commands():
    cmd = "npx -y @modelcontextprotocol/server-memory"
    assert cleaning.normalize_url(cmd) == cmd


def test_sanitize_text_strips_html_and_collapses_whitespace():
    assert cleaning.sanitize_text("<b>Hello</b>   world &amp; friends") == "Hello world & friends"


def test_clean_record_deduplicates_categories():
    rec = {
        "name": "X", "vendor": "Y", "docs_url": "https://x.com/docs",
        "server_url": "https://x.com/mcp", "source_url": "https://x.com/docs",
        "categories": ["Dev Tools", "Dev Tools", "Cloud"],
    }
    cleaned = cleaning.clean_record(rec)
    assert cleaned["categories"] == ["Cloud", "Dev Tools"]


# ---------- normalization.py ----------

def test_canonical_vendor_resolves_known_alias():
    assert normalization.canonical_vendor("github") == "GitHub"
    assert normalization.canonical_vendor("huggingface") == "Hugging Face"


def test_canonical_vendor_passes_through_unknown_names():
    assert normalization.canonical_vendor("Some New Vendor") == "Some New Vendor"


def test_find_fuzzy_candidates_flags_near_duplicates_but_not_identical():
    names = ["Notion", "Notion", "Notionn", "Slack"]
    candidates = normalization.find_fuzzy_candidates(names, cutoff=0.85)
    pairs = {(a, b) for a, b, _ in candidates}
    assert ("Notion", "Notionn") in pairs or ("Notionn", "Notion") in pairs
    assert ("Notion", "Slack") not in pairs


# ---------- deduplication.py ----------

def test_dedupe_removes_exact_duplicate_and_keeps_more_complete_record():
    records = [
        {"name": "GitHub MCP Server", "vendor_domain": "github.com", "auth_type": "Unknown", "server_url": ""},
        {"name": "GitHub MCP Server", "vendor_domain": "github.com", "auth_type": "Bearer Token", "server_url": "https://api.githubcopilot.com/mcp/"},
    ]
    out = deduplication.dedupe(records)
    assert len(out) == 1
    assert out[0]["auth_type"] == "Bearer Token"


def test_dedupe_keeps_distinct_records():
    records = [
        {"name": "A", "vendor_domain": "a.com"},
        {"name": "B", "vendor_domain": "b.com"},
    ]
    assert len(deduplication.dedupe(records)) == 2


# ---------- classification.py ----------

def test_classify_adds_entity_type_and_mcp_category():
    rec = {"categories": ["Dev Tools"]}
    out = classification.classify([rec])[0]
    assert out["entity_type"] == "mcp"
    assert "MCP" in out["categories"]


# ---------- validation.py ----------

def _valid_shaped_record(**overrides):
    base = {
        "id": "id-1", "entity_type": "mcp", "name": "X",
        "description": "A description.", "url": "https://x.com/docs",
        "categories": ["MCP"], "source": {"name": "X", "url": "https://x.com/docs"},
    }
    base.update(overrides)
    return base


def test_validate_accepts_well_formed_record():
    out = validation.validate([_valid_shaped_record()])
    assert len(out) == 1


def test_validate_drops_record_missing_required_field():
    rec = _valid_shaped_record()
    del rec["description"]
    assert validation.validate([rec]) == []


def test_validate_drops_record_with_malformed_url():
    rec = _valid_shaped_record(url="not-a-url")
    assert validation.validate([rec]) == []


def test_validate_drops_duplicate_ids_keeping_first():
    rec1 = _valid_shaped_record(id="dup")
    rec2 = _valid_shaped_record(id="dup", name="Y")
    out = validation.validate([rec1, rec2])
    assert len(out) == 1
    assert out[0]["name"] == "X"


def test_validate_allows_local_install_command_as_url():
    rec = _valid_shaped_record(url="npx -y @modelcontextprotocol/server-memory")
    assert len(validation.validate([rec])) == 1


# ---------- shaping.py ----------

def test_shape_mcp_record_produces_expected_schema_keys():
    rec = {
        "name": "Notion MCP Server", "vendor": "Notion", "vendor_domain": "notion.com",
        "docs_url": "https://developers.notion.com/docs/mcp",
        "server_url": "https://mcp.notion.com/mcp", "auth_type": "OAuth",
        "transport": "Remote/HTTP", "runtime": "Remote endpoint",
        "categories": ["Productivity", "MCP"], "description": "desc",
        "source_name": "Notion Developers", "source_url": "https://developers.notion.com/docs/mcp",
        "verification_tier": "verified",
    }
    shaped = shaping.shape_mcp_record(rec)
    for key in ("id", "entity_type", "name", "description", "url", "logo_url",
                "categories", "source", "verification_status", "metadata"):
        assert key in shaped
    assert shaped["metadata"]["vendor"] == "Notion"
    assert shaped["verification_status"] == "verified"


def test_shape_mcp_record_community_tier_uses_github_avatar_and_tier_label():
    rec = {
        "name": "Some Filesystem MCP", "vendor": "someuser", "vendor_domain": "github.com",
        "docs_url": "https://github.com/someuser/some-mcp", "server_url": "npx some-mcp",
        "auth_type": "Varies", "transport": "Local/stdio", "runtime": "npm package",
        "categories": ["Community", "MCP"], "description": "desc",
        "source_name": "MCP Registry", "source_url": "https://registry.modelcontextprotocol.io/v0/servers",
        "verification_tier": "community_github_verified",
        "repo_owner": "someuser", "repo_name": "some-mcp",
        "repo_url": "https://github.com/someuser/some-mcp",
    }
    shaped = shaping.shape_mcp_record(rec)
    assert shaped["verification_status"] == "community_github_verified"
    assert shaped["logo_url"] == "https://github.com/someuser.png"
    assert shaped["metadata"]["repository"]["url"] == "https://github.com/someuser/some-mcp"


def test_shape_mcp_record_same_name_different_repo_gets_different_id():
    base = {
        "vendor": "x", "vendor_domain": "github.com", "docs_url": "https://x.com",
        "server_url": "", "auth_type": "", "transport": "", "runtime": "",
        "categories": [], "description": "", "source_name": "x", "source_url": "https://x.com",
        "verification_tier": "community_github_verified", "repo_owner": "a", "repo_name": "r",
    }
    rec1 = {**base, "name": "Filesystem", "repo_url": "https://github.com/a/r"}
    rec2 = {**base, "name": "Filesystem", "repo_url": "https://github.com/b/r2"}
    assert shaping.shape_mcp_record(rec1)["id"] != shaping.shape_mcp_record(rec2)["id"]


def test_shape_mcp_record_id_is_stable_across_calls():
    rec = {
        "name": "A", "vendor": "V", "vendor_domain": "v.com", "docs_url": "https://v.com",
        "server_url": "", "auth_type": "", "transport": "", "runtime": "",
        "categories": [], "description": "", "source_name": "V", "source_url": "https://v.com",
    }
    assert shaping.shape_mcp_record(rec)["id"] == shaping.shape_mcp_record(rec)["id"]


def test_dedup_key_uses_repo_url_not_shared_github_domain():
    """Regression test: all community records share vendor_domain='github.com',
    so dedup must not collapse distinct repos into one just because their
    domain matches."""
    records = [
        {"name": "Filesystem", "vendor_domain": "github.com", "repo_url": "https://github.com/a/r1"},
        {"name": "Filesystem", "vendor_domain": "github.com", "repo_url": "https://github.com/b/r2"},
    ]
    assert len(deduplication.dedupe(records)) == 2


def test_descriptions_curated_lookup_is_tier_aware_not_name_only():
    """Regression test: a community record can coincidentally share a name
    with a first-party curated record (e.g. both named 'Filesystem') — the
    curated description must NOT leak onto the community record."""
    first_party = {
        "name": "Filesystem", "vendor": "Anthropic / MCP Steering Group",
        "categories": ["Reference"], "verification_tier": "verified",
        "publisher_description": "",
    }
    community = {
        "name": "Filesystem", "vendor": "someuser",
        "categories": ["Community"], "verification_tier": "community_github_verified",
        "publisher_description": "A totally different community filesystem server.",
    }
    out = descriptions.generate([first_party, community])
    fp_out = next(r for r in out if r["vendor"] == "Anthropic / MCP Steering Group")
    comm_out = next(r for r in out if r["vendor"] == "someuser")
    assert fp_out["description"] != comm_out["description"]
    assert comm_out["description"] == "A totally different community filesystem server."
    assert comm_out["description_source"] == "publisher_registry"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
