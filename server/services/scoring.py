"""
services.scoring — composite confidence score (SoW §6.2 / §6.3).

Pure functions, no I/O — trivially unit-testable. The matcher feeds in the raw
pgvector cosine similarity plus the boolean graph signals from Neo4j, and gets
back a final score clamped to [0, 1] together with the plain-language reason
labels the booth operator sees.

    base  = pgvector cosine similarity
    delta = sum of Neo4j graph modifiers
    final = clamp(base + delta, 0.0, 1.0)
"""

from __future__ import annotations

from collections.abc import Mapping

from schemas.common import ConfidenceBand

# ─────────────────────────────────────────────────────────────────────────────
# Modifier table — (delta, operator-facing label). Verbatim from SoW §6.2.
# Order is preserved so reason labels read in a stable, sensible sequence.
# ─────────────────────────────────────────────────────────────────────────────
MODIFIERS: dict[str, tuple[float, str]] = {
    "same_zone":              (+0.08, "Same zone ✓"),
    "adjacent_zone":          (+0.04, "Adjacent zone ✓"),
    "same_venue":             (+0.03, "Same venue ✓"),
    "different_venue":        (-0.12, "⚠ Different venue"),
    "same_city":              (+0.06, "Same city of origin ✓"),
    "same_state":             (+0.03, "Same state ✓"),
    "temporal_very_recent":   (+0.07, "Time gap under 2 hours ✓"),
    "temporal_same_day":      (+0.04, "Same day ✓"),
    "temporal_stale":         (-0.08, "⚠ Report over 3 days old"),
    "landmark_pattern_match": (+0.07, "Landmark pattern match ✓"),
    "language_match":         (+0.04, "Language spoken matches ✓"),
    "possible_duplicate":     (-0.05, "⚠ Possible duplicate report"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Confidence band thresholds (SoW §6.3). MIN_SURFACE is the floor below which a
# candidate is NOT shown to the operator at all.
# ─────────────────────────────────────────────────────────────────────────────
HIGH_THRESHOLD = 0.90
PROBABLE_THRESHOLD = 0.75
POSSIBLE_THRESHOLD = 0.60
MIN_SURFACE = POSSIBLE_THRESHOLD


def composite_confidence(
    vector_score: float,
    graph_signals: Mapping[str, bool],
) -> tuple[float, list[str]]:
    """
    Combine the vector similarity with the Neo4j graph signals.

    Args:
        vector_score: pgvector cosine similarity in [0, 1].
        graph_signals: mapping of signal-name -> bool (see schemas.GraphSignals).
            Unknown / missing keys are ignored, so a degraded Neo4j response
            simply contributes no modifiers (score == vector_score).

    Returns:
        (final_score, reason_labels) where final_score is rounded to 3 dp and
        clamped to [0, 1], and reason_labels are the human-readable strings for
        the signals that fired — in MODIFIERS order.
    """
    base = float(vector_score)
    reasons: list[str] = []

    for signal, (delta, label) in MODIFIERS.items():
        if graph_signals.get(signal):
            base += delta
            reasons.append(label)

    final = round(min(max(base, 0.0), 1.0), 3)
    return final, reasons


def confidence_band(score: float) -> ConfidenceBand | None:
    """
    Map a final score to its operator band, or None if below the surface floor.

    None means "do not show this candidate" — the matcher filters these out.
    """
    if score >= HIGH_THRESHOLD:
        return ConfidenceBand.high
    if score >= PROBABLE_THRESHOLD:
        return ConfidenceBand.probable
    if score >= POSSIBLE_THRESHOLD:
        return ConfidenceBand.possible
    return None
