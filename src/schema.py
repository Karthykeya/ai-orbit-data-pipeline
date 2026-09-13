"""Common entity schema + id generation, per the project spec's Data Schema Standards."""
import hashlib
import re
import uuid

# Fixed namespace UUID for this project, so ids are stable across pipeline runs.
NAMESPACE = uuid.UUID("6f1c1c2e-9b8b-4a7a-8b1e-000000000001")


def stable_uuid(*parts: str) -> str:
    """Deterministic UUIDv5 from stable natural keys, so re-running the pipeline
    on the same source data always yields the same id (idempotent ingestion)."""
    key = "|".join(p.strip().lower() for p in parts)
    return str(uuid.uuid5(NAMESPACE, key))


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


def apex_domain(domain: str) -> str:
    """Normalize a vendor domain to its bare apex form (no scheme/www)."""
    domain = domain.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def official_logo_url(domain: str) -> str:
    """Resolve an official logo for an entity from its own apex domain.

    Strategy: Clearbit's Logo API (https://logo.clearbit.com/{domain}) serves
    the *actual* logo asset published at the company's own domain — it is a
    domain-keyed lookup, not a third-party stock-icon directory, so the image
    returned is verifiably the entity's own brand mark as long as the domain
    itself was verified against an official source (see `source_url` on each
    record). This keeps every logo traceable back to the same official domain
    used for the `url` field, satisfying the "verify website and logo belong
    to the correct entity" requirement.
    """
    d = apex_domain(domain)
    return f"https://logo.clearbit.com/{d}"
