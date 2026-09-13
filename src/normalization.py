"""Normalization stage: canonicalize vendor/company name variants.

This is the "OpenAI vs Open AI" problem from the spec. We keep a small,
explicit alias map (rather than fuzzy string matching alone) because vendor
names are brand-sensitive and fuzzy matching alone risks merging distinct
companies with similar names (e.g. "Square" the payments company vs any
future unrelated "Square"). Fuzzy matching is used only as a secondary pass
to *surface candidates* for review, never to auto-merge silently.
"""
import difflib

CANONICAL_VENDOR_ALIASES = {
    "anthropic": "Anthropic",
    "anthropic / mcp steering group": "Anthropic / MCP Steering Group",
    "github": "GitHub",
    "github inc": "GitHub",
    "microsoft": "Microsoft",
    "google": "Google",
    "notion": "Notion",
    "notion labs": "Notion",
    "stripe": "Stripe",
    "stripe inc": "Stripe",
    "cloudflare": "Cloudflare",
    "cloudflare inc": "Cloudflare",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
}


def canonical_vendor(name: str) -> str:
    key = name.strip().lower()
    return CANONICAL_VENDOR_ALIASES.get(key, name.strip())


def find_fuzzy_candidates(names: list[str], cutoff: float = 0.9) -> list[tuple[str, str, float]]:
    """Return pairs of names that are suspiciously similar but not identical,
    for human review — never used to silently merge records."""
    candidates = []
    seen = set()
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a == b:
                continue
            pair = tuple(sorted((a, b)))
            if pair in seen:
                continue
            ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
            if ratio >= cutoff:
                candidates.append((a, b, round(ratio, 3)))
                seen.add(pair)
    return candidates


def normalize(records: list[dict]) -> list[dict]:
    out = []
    for rec in records:
        rec = dict(rec)
        rec["vendor"] = canonical_vendor(rec["vendor"])
        out.append(rec)
    return out
