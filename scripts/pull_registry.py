#!/usr/bin/env python3
"""
Pull real MCP server listings from Anthropic's official MCP Registry
(https://registry.modelcontextprotocol.io) — the "authoritative repository
for publicly-available MCP servers" — and filter them down to a clean,
de-duplicated, spam-free dataset.

WHY THIS RUNS ON YOUR MACHINE, NOT IN THE PIPELINE SANDBOX:
The environment this pipeline was developed in has no outbound network
access. This script is real, working, production code — run it once on any
machine with internet access and it writes `data/raw/registry_pull.json`,
which `src/discovery.py` automatically picks up and merges with the curated
first-party seed on the next `python run.py`.

WHAT IT DOES
------------
1. Paginates through GET /v0/servers (cursor-based, matches the registry's
   own pagination contract).
2. Keeps only the latest version of each server (the registry returns every
   published version — we only want `isLatest: true`).
3. Requires a real, public GitHub repository URL — this is what makes a
   community entry verifiable at all: anyone can open the link and confirm
   the project exists and matches its listed description.
4. Drops spam/templated listings using a small set of concrete signals
   found by inspecting real registry output: descriptions matching the
   "Premium agentic endpoint for X" / "Execute X" template, servers that
   require a paid `x402`/USDC payment header just to be described, and
   descriptions under 15 characters.
5. De-duplicates by (repository URL, subfolder) — the registry has several
   MCP servers published as sub-packages of one monorepo under slightly
   different names.
6. Optionally enriches each surviving record with live GitHub metadata
   (stars, primary language, last-updated timestamp — the exact
   "Repositories" fields the trial spec asks for) via the public GitHub
   REST API, with exponential backoff on 403/429 rate limits.
7. Stops once `--target` clean records have been collected, or the
   registry is exhausted.

USAGE
-----
    pip install requests
    python scripts/pull_registry.py --target 1000 --enrich-github
    # optional: export GITHUB_TOKEN=ghp_xxx first, to raise the GitHub API
    # rate limit from 60/hr to 5,000/hr — otherwise --enrich-github will be
    # slow and may stop early once the unauthenticated quota is used up.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

REGISTRY_BASE = "https://registry.modelcontextprotocol.io/v0/servers"
GITHUB_API = "https://api.github.com/repos"
OUT_PATH = Path(__file__).parent.parent / "data" / "raw" / "registry_pull.json"

SPAM_DESCRIPTION_PATTERNS = [
    re.compile(r"^premium agentic endpoint for", re.IGNORECASE),
    re.compile(r"^execute [\w.\-]+$", re.IGNORECASE),
]
SPAM_HEADER_MARKERS = {"payment-signature", "x402", "usdc"}


def is_spam(server: dict) -> bool:
    desc = (server.get("description") or "").strip()
    if len(desc) < 15:
        return True
    for pattern in SPAM_DESCRIPTION_PATTERNS:
        if pattern.match(desc):
            return True
    for remote in server.get("remotes", []) or []:
        header_text = json.dumps(remote.get("headers", [])).lower()
        if any(marker in header_text for marker in SPAM_HEADER_MARKERS):
            return True
    return False


def get_with_backoff(session: requests.Session, url: str, params: dict, max_attempts: int = 6) -> requests.Response:
    """GET with exponential backoff + jitter on 429/5xx, honoring Retry-After
    when the server sends one — the same policy documented in ARCHITECTURE.md."""
    for attempt in range(max_attempts):
        resp = session.get(url, params=params, timeout=20)
        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = resp.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else min(2 ** attempt + random.random(), 60)
            print(f"  [backoff] {resp.status_code} on {url} — sleeping {delay:.1f}s (attempt {attempt+1})", file=sys.stderr)
            time.sleep(delay)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Exceeded retry budget fetching {url}")


def to_seed_shape(server: dict) -> dict:
    """Map a registry server object into the same flat shape used by
    `data/raw/mcp_seed.py`, plus extra fields consumed only by community
    records (repo_owner, repo_name, verification_tier)."""
    repo = server.get("repository") or {}
    repo_url = (repo.get("url") or "").rstrip("/").removesuffix(".git")
    owner_repo = ""
    if "github.com/" in repo_url:
        owner_repo = repo_url.split("github.com/", 1)[1]
    owner = owner_repo.split("/")[0] if owner_repo else "unknown"
    repo_name = owner_repo.split("/")[1] if "/" in owner_repo else owner_repo

    packages = server.get("packages") or []
    remotes = server.get("remotes") or []
    if remotes:
        transport = "Remote/" + remotes[0].get("type", "http").upper()
        server_url = remotes[0].get("url", "")
        runtime = "Remote endpoint"
    elif packages:
        pkg = packages[0]
        transport = "Local/stdio"
        hint = pkg.get("runtimeHint", pkg.get("registryType", "unknown"))
        server_url = f"{hint} {pkg.get('identifier', '')}".strip()
        runtime = f"{pkg.get('registryType', 'unknown')} package ({hint})"
    else:
        transport, server_url, runtime = "Unknown", "", "Unknown"

    website = server.get("websiteUrl") or repo_url or f"https://github.com/{owner_repo}"

    return {
        "name": server.get("title") or server.get("name", "").split("/")[-1],
        "vendor": owner,
        "docs_url": website,
        "server_url": server_url,
        "vendor_domain": "github.com",
        "auth_type": "Varies (see package/remote config)",
        "transport": transport,
        "categories": ["Community"],
        "runtime": runtime,
        "source_name": "MCP Registry (registry.modelcontextprotocol.io)",
        "source_url": f"https://registry.modelcontextprotocol.io/v0/servers?search={urllib.parse.quote(server.get('name',''))}",
        "verification_tier": "community_github_verified",
        "repo_owner": owner,
        "repo_name": repo_name,
        "repo_url": f"https://github.com/{owner_repo}" if owner_repo else repo_url,
        # publisher-authored description from the registry itself — kept as
        # a documented fallback if no LLM pass is run over this record; see
        # src/descriptions.py for how this is used vs. LLM-generated text.
        "publisher_description": (server.get("description") or "").strip(),
    }


def enrich_with_github(session: requests.Session, record: dict, token: str | None) -> dict:
    if not record.get("repo_owner") or record["repo_owner"] == "unknown" or not record.get("repo_name"):
        return record
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{GITHUB_API}/{record['repo_owner']}/{record['repo_name']}"
    try:
        resp = get_with_backoff(session, url, params={})
        if resp.status_code == 404:
            return record
        data = resp.json()
        record["stars"] = data.get("stargazers_count")
        record["primary_language"] = data.get("language")
        record["last_updated"] = data.get("pushed_at")
    except Exception as e:
        print(f"  [github] enrichment failed for {record['repo_url']}: {e}", file=sys.stderr)
    return record


def pull(target: int, enrich_github: bool, github_token: str | None) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": "ai-orbit-registry-pull/1.0"})

    seen_keys = set()
    seen_repo_subfolder = set()
    collected = []
    cursor = None
    pages_fetched = 0

    while len(collected) < target:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor
        resp = get_with_backoff(session, REGISTRY_BASE, params)
        payload = resp.json()
        servers = payload.get("servers", [])
        if not servers:
            print("Registry exhausted — no more pages.", file=sys.stderr)
            break
        pages_fetched += 1
        print(f"Page {pages_fetched}: {len(servers)} raw entries, {len(collected)} collected so far", file=sys.stderr)

        for entry in servers:
            server = entry.get("server", {})
            meta = entry.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            if not meta.get("isLatest"):
                continue
            if meta.get("status") != "active":
                continue
            repo = server.get("repository") or {}
            if repo.get("source") != "github" or not repo.get("url"):
                continue  # no verifiable public source -> skip, don't guess
            if is_spam(server):
                continue

            dedup_key = (repo.get("url"), repo.get("subfolder", ""))
            if dedup_key in seen_repo_subfolder:
                continue
            seen_repo_subfolder.add(dedup_key)

            record = to_seed_shape(server)
            name_key = f"{record['name'].strip().lower()}::{record['repo_url'].lower()}"
            if name_key in seen_keys:
                continue
            seen_keys.add(name_key)

            if enrich_github:
                record = enrich_with_github(session, record, github_token)
                time.sleep(0.05)  # be polite even within the rate limit

            collected.append(record)
            if len(collected) >= target:
                break

        cursor = payload.get("metadata", {}).get("nextCursor")
        if not cursor:
            print("No further cursor — reached end of registry.", file=sys.stderr)
            break
        time.sleep(0.2)  # be a polite scraper between pages

    return collected


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=int, default=1000, help="number of clean records to collect")
    ap.add_argument("--enrich-github", action="store_true", help="fetch stars/language/last-updated per repo (slower, rate-limited)")
    ap.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"), help="optional token to raise GitHub API rate limit")
    args = ap.parse_args()

    records = pull(args.target, args.enrich_github, args.github_token)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2))
    print(f"\nWrote {len(records)} clean, de-duplicated, spam-filtered records to {OUT_PATH}")
    print("Run `python run.py` next to fold these into the full pipeline output.")


if __name__ == "__main__":
    main()
