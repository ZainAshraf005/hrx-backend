import re
import unicodedata
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

SLUG_MAX_LENGTH = 120


def slugify(value: str, fallback: str = "item") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    slug = slug[:SLUG_MAX_LENGTH].rstrip("-")
    return slug or fallback


def slug_with_suffix(base: str, suffix: int) -> str:
    suffix_text = f"-{suffix}"
    trimmed_base = base[: SLUG_MAX_LENGTH - len(suffix_text)].rstrip("-")
    return f"{trimmed_base}{suffix_text}"


async def allocate_unique_slug(
    db: AsyncSession,
    model: Any,
    value: str,
    *scope_filters: Any,
) -> str:
    base = slugify(value, fallback=model.__tablename__.rstrip("s"))
    result = await db.execute(
        select(model.slug).where(
            *scope_filters,
            or_(model.slug == base, model.slug.like(f"{base}-%")),
        )
    )
    existing = set(result.scalars().all())
    if base not in existing:
        return base

    suffix = 2
    while slug_with_suffix(base, suffix) in existing:
        suffix += 1
    return slug_with_suffix(base, suffix)
