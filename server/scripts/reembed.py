"""
scripts.reembed — recompute text embeddings for every stored report.

The synthetic corpus was originally embedded with the deterministic STUB embedder
(EMBEDDING_FALLBACK=1 / model not installed), which is reproducible but NOT
semantic. Once the real multilingual-e5-large model is installed and
EMBEDDING_FALLBACK=0, run this once to re-embed the existing rows so pgvector
similarity search returns genuinely semantically-similar candidates.

It batch-encodes `physical_description` for all missing_reports and found_reports
and writes the new `embedding` column. Idempotent — safe to re-run.

Usage (must run with the real model available, i.e. EMBEDDING_FALLBACK=0):
    python -m scripts.reembed
    python -m scripts.reembed --batch 128
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from core.config import settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from db.models import FoundReport, MissingReport  # noqa: E402
from services import embedding  # noqa: E402

log = get_logger("reembed")


async def _reembed_model(model_cls, batch_size: int) -> int:
    """Re-embed every row of one report table; returns the count updated."""
    updated = 0
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(model_cls))).scalars().all()
        log.info("%s: %d rows to re-embed", model_cls.__tablename__, len(rows))
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
            for r in chunk:
                # kind="passage" — stored documents use the e5 passage prefix so
                # they line up with the matcher's "query" embedding convention.
                r.embedding = embedding.embed_text(r.physical_description or "—", kind="passage")
            await s.commit()
            updated += len(chunk)
            log.info("  %s: %d/%d", model_cls.__tablename__, updated, len(rows))
    return updated


async def main(batch_size: int) -> None:
    if settings.EMBEDDING_FALLBACK:
        log.warning(
            "EMBEDDING_FALLBACK is ON — re-embedding with the STUB embedder is a "
            "no-op for semantics. Set EMBEDDING_FALLBACK=0 with the real model first."
        )
    m = await _reembed_model(MissingReport, batch_size)
    f = await _reembed_model(FoundReport, batch_size)
    print(f"✅ re-embedded {m} missing + {f} found reports with {settings.EMBEDDING_MODEL}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Recompute text embeddings for all reports.")
    ap.add_argument("--batch", type=int, default=64, help="rows per encode/commit batch")
    args = ap.parse_args()
    asyncio.run(main(args.batch))
