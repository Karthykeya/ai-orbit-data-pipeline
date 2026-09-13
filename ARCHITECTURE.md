# Architecture

This document covers how the pipeline's design decisions extend past the
~75-record MCP module built for this submission, toward the spec's full
scope (250–300+ records across 14 categories, with headroom well beyond
that). It answers the four questions that matter most once an ingestion
pipeline needs to run unattended, repeatedly, and at volume: scaling to
500k+ records, handling upstream rate limits, deduplicating across
concurrent workers, and where the data lives at each stage.

## 1. Scaling to 500k+ records

The current pipeline is intentionally single-process and in-memory — the
right choice at hundreds of records, the wrong choice at hundreds of
thousands. Three things change, in order of when they'd actually bite:

**Partition discovery by source, not by record.** Each of the 14 categories
in the spec (Tools, Models, Repositories, MCP, News, Videos, ...) maps to a
different discovery source with a different rate limit and pagination
model (GitHub Search API, Hugging Face Hub API, YouTube Data API, RSS
polling, vendor sitemaps). At volume, `discovery.py` for each category
becomes an independent worker that can run on its own schedule and its own
concurrency budget, rather than one `discover()` call blocking on the
slowest source. This pipeline's `discovery.py` already returns a plain list
of dicts precisely so it can be swapped for "read the next page of results
from a queue" without touching downstream stages.

**Move from list-of-dicts to a streaming/batch contract between stages.**
Every stage here (`extract`, `clean`, `normalize`, `dedupe`, `classify`,
`generate`, `shape`, `validate`) is a pure function `list[dict] -> list[dict]`.
That's the right shape for correctness and testing at small N, and it's
also the right shape to convert into `Iterable[dict]` generators once N is
too large to hold in memory — no stage's *logic* needs to change, only how
records are handed between them (e.g. batches of 5,000 written to Parquet
between stages instead of one big JSON list).

**Push deduplication and id assignment earlier, not later.** Right now
`deduplication.py` operates on the whole in-memory batch after cleaning.
At 500k+ records that's still fine within a single category (dedup keys are
small — `slug(name) + domain` — so an in-memory hash set holds millions of
keys comfortably), but cross-category and cross-source dedup (the same
tool discovered via GitHub *and* a directory site) needs a shared,
persistent key-value store rather than a per-run Python dict — see §3.

## 2. Handling 429 (rate limit) and 413 (payload too large)

None of this pipeline's current sources required aggressive backoff at 75
records, but the design anticipates it:

- **429 (rate limited):** every `discovery.py`/enrichment call that hits a
  real API (GitHub Search, Hugging Face Hub, a vendor's docs API) should be
  wrapped in exponential backoff with jitter, keyed by *host*, not by
  request — e.g. `tenacity`'s `wait_exponential_jitter` triggered
  specifically on HTTP 429, reading `Retry-After` when the API sends one
  rather than guessing. Backoff state is tracked per-domain in a shared
  dict/Redis key so concurrent workers hitting the same host share the same
  cooldown instead of each independently re-triggering the limit.
- **413 (payload too large):** this hits two places — (a) sending too much
  scraped HTML/text to the description-generation LLM call in
  `descriptions.py`, and (b) writing overly large batched JSON payloads to
  storage. The fix in both cases is pre-emptive chunking rather than
  reactive retry: cap raw text handed to `generate_via_llm()` at a fixed
  character budget per record (truncate + summarize signal fields first,
  full text last), and write JSON outputs in fixed-size batches (e.g. 5,000
  records per file) rather than one monolithic file once volume grows past
  what fits comfortably in a single write.

## 3. Cross-node deduplication & freshness

Once discovery runs as multiple concurrent workers (one per source or
category) rather than one sequential script, two workers can independently
discover the same entity before either has written its result — the
in-memory `dict` keyed by `slug(name) + domain` in this submission's
`deduplication.py` doesn't see across processes.

The fix is a shared, atomic **claim-check store**: before a worker starts
extracting a candidate record, it does an atomic
`SETNX dedup:<slug(name)>:<domain>` (Redis) or an `INSERT ... ON CONFLICT
DO NOTHING` (Postgres/SQLite — the pattern a peer submission's
`ON CONFLICT(url) DO UPDATE` uses). Whichever worker wins the race proceeds
to write the full record; the loser discards its candidate rather than both
writing near-duplicate rows that a later batch job has to reconcile. This
pipeline's `schema.stable_uuid()` already generates the same id from the
same natural key on every run — replacing the in-memory dedup dict with
that same key checked against a shared store is a drop-in change, not a
redesign.

**Freshness** (re-crawling entities whose data may have changed, e.g. a
GitHub repo's star count) works the same way: every record would carry a
`last_verified_at` timestamp alongside `verification_status`, and a
scheduled re-discovery pass only re-fetches records older than a TTL
appropriate to that category (GitHub stars: daily; a company's
headquarters: essentially never) rather than re-crawling the whole dataset
on every run.

## 4. Storage strategy

| Stage | Storage | Why |
|---|---|---|
| Raw discovery/extraction output | Append-only object storage (e.g. S3-compatible), one file per source per run | Cheap, durable, replayable — if a downstream bug corrupts cleaned output, raw input is still there to reprocess without re-hitting rate-limited APIs |
| Working records mid-pipeline | Row-oriented Parquet in batches | Efficient for the columnar-ish transforms (clean/normalize/classify) each stage does over many records |
| Deduplication keys | Redis (or a Postgres unique index) | Needs atomic claim-check semantics across concurrent workers, not just fast lookup |
| Final entity + relationship records | Postgres (or any RDBMS) as source of truth, with the flat JSON files this submission ships as a generated export | Relationships between entities (Company→Tool, MCP→Tool) are naturally foreign keys; a relational store also gives cheap integrity constraints (`validation.py`'s checks become `NOT NULL` / `CHECK` constraints instead of Python assertions) |
| Google Sheet / downstream JSON | Generated artifacts, not the source of truth | Regenerated from the database on every publish, matching this submission's `run.py` → `build_sheet.py` flow, just with a DB read in place of the static seed |

This submission's actual data volume (75 records) doesn't need any of this
— a single Python process and three JSON files is the right-sized solution
at this scale, per the spec's own "Architecture ... Modular, reusable, and
scalable code" criterion, which rewards a design that scales, not a
prematurely distributed system for 75 rows. This document exists to show
the specific points where the current design would change, and why those
particular points, when volume demands it.
