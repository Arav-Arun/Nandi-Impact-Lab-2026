"""
services.embedding - multilingual text embeddings (Member 1).

Public contract (relied on by intake and the matcher):

    embed_text(text: str, kind: str = "passage") -> list[float]   # len == EMBEDDING_DIM (1024)

Design notes
------------
The real model (intfloat/multilingual-e5-large) is large and GPU-friendly. So the
rest of the system stays buildable on any laptop, this module:

  • Lazy-loads the real model only on first use (never at import time).
  • Falls back to a DETERMINISTIC stub embedder when EMBEDDING_FALLBACK=1 or when
    the real model cannot be loaded. The stub hashes the input to seed a fixed
    pseudo-random unit vector, so:
        - identical text  -> identical vector (cosine 1.0)
        - similar text    -> NOT semantically similar (it's a hash), but matching
          and tests remain reproducible and the pipeline runs end-to-end.
    Set EMBEDDING_FALLBACK=0 (with the model installed) for real multilingual
    semantics - the default in this deployment.

e5 prefix convention: stored documents are embedded as "passage: ..." and search
queries as "query: ...". `kind` selects the prefix.
"""

from __future__ import annotations

import hashlib

import numpy as np

from core.config import settings
from core.logging_utils import get_logger

log = get_logger(__name__)

# Lazily-initialised singleton for the real model. None until first real use.
_text_model = None  # sentence_transformers.SentenceTransformer
# Once the real model fails to load we stop retrying and use the stub for the
# rest of the process lifetime (avoids hammering a missing dependency per call).
_text_real_unavailable = False


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic stub embedder (dev / test / no-GPU fallback)
# ─────────────────────────────────────────────────────────────────────────────
def _stub_vector(text: str, dim: int) -> list[float]:
    """
    Hash `text` to a fixed unit vector of length `dim`.

    Deterministic: same input → same output, so cosine similarity of identical
    descriptions is exactly 1.0 and tests are reproducible. Not semantic.
    """
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm  # L2-normalise → cosine distance behaves like dot product
    return vec.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# Text embedding (multilingual-e5-large)
# ─────────────────────────────────────────────────────────────────────────────
def _load_text_model():
    """Load the sentence-transformers model once; mark unavailable on failure."""
    global _text_model, _text_real_unavailable
    if _text_model is not None:
        return _text_model
    try:
        from sentence_transformers import SentenceTransformer

        log.info("Loading text embedding model %s (device=%s) …",
                 settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE)
        _text_model = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
        return _text_model
    except Exception as exc:  # model missing / OOM / offline
        log.warning("Real text model unavailable (%s); using deterministic stub.", exc)
        _text_real_unavailable = True
        return None


def embed_text(text: str, kind: str = "passage") -> list[float]:
    """
    Embed a piece of text into a `settings.EMBEDDING_DIM`-dim vector.

    Args:
        text: freeform description, any language (Marathi/Hindi/Telugu/mixed).
        kind: "passage" for stored documents, "query" for search inputs (e5
            asymmetric prefix). Anything else is treated as "passage".

    Returns:
        A list[float] of length settings.EMBEDDING_DIM, L2-normalised.
    """
    prefix = "query" if kind == "query" else "passage"
    prepared = f"{prefix}: {text or ''}"

    use_stub = settings.EMBEDDING_FALLBACK or _text_real_unavailable
    if not use_stub:
        model = _load_text_model()
        if model is not None:
            # normalize_embeddings=True so cosine distance is well-behaved.
            vec = model.encode(prepared, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32).tolist()

    # Fallback path - seed the stub with the prepared (prefixed) string so the
    # passage/query distinction is preserved deterministically.
    return _stub_vector(prepared, settings.EMBEDDING_DIM)
