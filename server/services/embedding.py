"""
services.embedding — text + face embeddings (Member 1).

Public contract (relied on by M2's intake and M1's matcher):

    embed_text(text: str, kind: str = "passage") -> list[float]   # len == EMBEDDING_DIM (1024)
    embed_face(image_bytes: bytes)               -> list[float] | None  # len == FACE_EMBEDDING_DIM (512)

Design notes
------------
The real models (intfloat/multilingual-e5-large, InsightFace buffalo_l) are
large and GPU-friendly. To keep the rest of the system buildable on a laptop —
and so M2/M3/M4 are never blocked on a multi-GB download — this module:

  • Lazy-loads the real model only on first use (never at import time).
  • Falls back to a DETERMINISTIC stub embedder when EMBEDDING_FALLBACK=1 (the
    default) or when the real model cannot be loaded. The stub hashes the input
    to seed a fixed pseudo-random unit vector, so:
        - identical text  -> identical vector (cosine 1.0)
        - similar text    -> NOT semantically similar (it's a hash), but matching
          and tests remain reproducible and the pipeline runs end-to-end.
    Flip EMBEDDING_FALLBACK=0 on the demo box (with the model installed) for real
    multilingual semantics.

e5 prefix convention (SoW §12.5): stored documents are embedded as "passage: ..."
and search queries as "query: ...". `kind` selects the prefix.
"""

from __future__ import annotations

import hashlib

import numpy as np

from core.config import settings
from core.logging_utils import get_logger

log = get_logger(__name__)

# Lazily-initialised singletons for the real models. None until first real use.
_text_model = None  # sentence_transformers.SentenceTransformer
_face_model = None  # insightface.app.FaceAnalysis
# Once a real model fails to load we stop retrying and use the stub for the
# rest of the process lifetime (avoids hammering a missing dependency per call).
_text_real_unavailable = False
_face_real_unavailable = False


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

    # Fallback path — seed the stub with the prepared (prefixed) string so the
    # passage/query distinction is preserved deterministically.
    return _stub_vector(prepared, settings.EMBEDDING_DIM)


# ─────────────────────────────────────────────────────────────────────────────
# Face embedding (InsightFace buffalo_l / ArcFace, 512-dim)
# ─────────────────────────────────────────────────────────────────────────────
def _load_face_model():
    """Load InsightFace once; mark unavailable on failure (deps are optional)."""
    global _face_model, _face_real_unavailable
    if _face_model is not None:
        return _face_model
    try:
        from insightface.app import FaceAnalysis

        log.info("Loading face model %s …", settings.FACE_MODEL)
        app = FaceAnalysis(name=settings.FACE_MODEL)
        app.prepare(ctx_id=0 if settings.EMBEDDING_DEVICE != "cpu" else -1)
        _face_model = app
        return _face_model
    except Exception as exc:
        log.warning("Real face model unavailable (%s); using deterministic stub.", exc)
        _face_real_unavailable = True
        return None


def embed_face(image_bytes: bytes) -> list[float] | None:
    """
    Embed the largest detected face in `image_bytes` into a 512-dim vector.

    Returns None when no face is detected (caller treats faceless photos as "no
    face vector" — photos are optional everywhere, SoW §12.8 #5). In stub mode a
    vector is always returned (hash of the image bytes) so the re-rank path is
    still exercised in tests.
    """
    if not image_bytes:
        return None

    use_stub = settings.EMBEDDING_FALLBACK or _face_real_unavailable
    if not use_stub:
        app = _load_face_model()
        if app is not None:
            try:
                import cv2  # provided by opencv via insightface

                arr = np.frombuffer(image_bytes, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                faces = app.get(img)
                if not faces:
                    return None
                # Pick the largest face by bounding-box area.
                face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                emb = np.asarray(face.normed_embedding, dtype=np.float32)
                return emb.tolist()
            except Exception as exc:
                log.warning("Face embedding failed (%s); using stub.", exc)

    # Fallback — deterministic per image content.
    digest = hashlib.sha256(image_bytes).hexdigest()
    return _stub_vector(f"face:{digest}", settings.FACE_EMBEDDING_DIM)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two embedding vectors, clamped to [-1, 1].

    Used by the photo re-ranking step. Returns 0.0 if either vector is empty or
    zero-length (treated as "no signal").
    """
    # NB: a/b may be numpy arrays (pgvector returns ndarray) — never use bare
    # truthiness on them (it raises "ambiguous truth value"). Check None/size.
    if a is None or b is None:
        return 0.0
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    if va.size == 0 or vb.size == 0:
        return 0.0
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.clip(np.dot(va, vb) / (na * nb), -1.0, 1.0))
