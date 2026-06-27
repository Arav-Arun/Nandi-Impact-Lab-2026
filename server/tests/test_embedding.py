"""
tests.test_embedding — unit tests for services.embedding in stub/fallback mode.

EMBEDDING_FALLBACK=1 is pinned in conftest, so embed_text / embed_face use the
deterministic hash-seeded stub. We verify the public contract M2 and the matcher
rely on:
  • embed_text → length-1024, L2-normalised, deterministic (cosine 1.0 on repeat),
  • passage vs query prefixes produce different vectors,
  • embed_face → length-512 (and None for empty input),
  • cosine_similarity behaves (identical = 1.0, orthogonal ≈ 0, empty = 0).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.config import settings
from services.embedding import cosine_similarity, embed_face, embed_text


def _l2_norm(vec: list[float]) -> float:
    return float(np.linalg.norm(np.asarray(vec, dtype=np.float64)))


# ─────────────────────────────────────────────────────────────────────────────
# Sanity: we really are in stub mode
# ─────────────────────────────────────────────────────────────────────────────
def test_fallback_mode_is_active() -> None:
    assert settings.EMBEDDING_FALLBACK is True


# ─────────────────────────────────────────────────────────────────────────────
# embed_text
# ─────────────────────────────────────────────────────────────────────────────
def test_embed_text_length_is_1024() -> None:
    vec = embed_text("a man in a blue kurta near Ramkund")
    assert len(vec) == 1024
    assert len(vec) == settings.EMBEDDING_DIM


def test_embed_text_is_l2_normalised() -> None:
    vec = embed_text("लाल साडीतील वृद्ध महिला")  # Marathi description
    assert _l2_norm(vec) == pytest.approx(1.0, abs=1e-5)


def test_embed_text_is_all_floats() -> None:
    vec = embed_text("child, approx 7 years, green shirt")
    assert all(isinstance(x, float) for x in vec)


def test_embed_text_is_deterministic() -> None:
    text = "elderly man, white dhoti, walking stick"
    a = embed_text(text)
    b = embed_text(text)
    assert a == b  # bit-for-bit identical
    assert cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-6)


def test_embed_text_different_inputs_differ() -> None:
    a = embed_text("a tall man with a red turban")
    b = embed_text("a short woman with a yellow saree")
    assert a != b
    # Random unit vectors in 1024-d are near-orthogonal, well below 1.0.
    assert cosine_similarity(a, b) < 0.5


def test_passage_and_query_prefixes_differ() -> None:
    """e5 asymmetric prefixes (SoW §12.5): passage: vs query: must differ."""
    text = "missing boy near the main ghat"
    passage = embed_text(text, kind="passage")
    query = embed_text(text, kind="query")
    assert passage != query
    assert cosine_similarity(passage, query) < 0.99


def test_default_kind_is_passage() -> None:
    text = "woman in green, age 40"
    assert embed_text(text) == embed_text(text, kind="passage")


def test_unknown_kind_is_treated_as_passage() -> None:
    text = "boy, 8 years old"
    assert embed_text(text, kind="banana") == embed_text(text, kind="passage")


def test_empty_text_is_handled() -> None:
    vec = embed_text("")
    assert len(vec) == 1024
    assert _l2_norm(vec) == pytest.approx(1.0, abs=1e-5)


# ─────────────────────────────────────────────────────────────────────────────
# embed_face
# ─────────────────────────────────────────────────────────────────────────────
def test_embed_face_length_is_512() -> None:
    vec = embed_face(b"\x89PNG\r\n\x1a\n fake image bytes for the stub")
    assert vec is not None
    assert len(vec) == 512
    assert len(vec) == settings.FACE_EMBEDDING_DIM


def test_embed_face_is_normalised_and_deterministic() -> None:
    img = b"some-bytes-representing-a-jpeg"
    a = embed_face(img)
    b = embed_face(img)
    assert a == b
    assert _l2_norm(a) == pytest.approx(1.0, abs=1e-5)


def test_embed_face_empty_bytes_returns_none() -> None:
    assert embed_face(b"") is None
    assert embed_face(None) is None  # type: ignore[arg-type]


def test_embed_face_distinct_images_differ() -> None:
    a = embed_face(b"image-one")
    b = embed_face(b"image-two")
    assert a != b


# ─────────────────────────────────────────────────────────────────────────────
# cosine_similarity
# ─────────────────────────────────────────────────────────────────────────────
def test_cosine_identical_is_one() -> None:
    v = embed_text("a person")
    assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_orthogonal_is_zero() -> None:
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-9)


def test_cosine_opposite_is_minus_one() -> None:
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-9)


def test_cosine_is_clamped_to_unit_interval() -> None:
    # Even with un-normalised inputs the result stays within [-1, 1].
    a = [3.0, 4.0]  # norm 5
    b = [6.0, 8.0]  # parallel → cosine 1.0
    sim = cosine_similarity(a, b)
    assert -1.0 <= sim <= 1.0
    assert sim == pytest.approx(1.0, abs=1e-6)


def test_cosine_empty_or_zero_vectors_return_zero() -> None:
    assert cosine_similarity([], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_cosine_known_angle() -> None:
    """45-degree vectors give cos(45°) ≈ 0.7071."""
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    assert cosine_similarity(a, b) == pytest.approx(math.cos(math.radians(45)), abs=1e-6)
