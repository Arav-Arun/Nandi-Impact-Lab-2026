"""
tests.test_scoring — unit tests for services.scoring (no I/O, no DB).

Locks down the SoW §6.2 / §6.3 contract:
  • every modifier's exact delta and operator-facing label,
  • clamping to [0, 1],
  • rounding to 3 decimal places,
  • band thresholds (≥0.90 high, ≥0.75 probable, ≥0.60 possible, <0.60 → None),
  • reason labels emitted in MODIFIERS order.
"""

from __future__ import annotations

import pytest

from schemas.common import ConfidenceBand
from services import scoring
from services.scoring import (
    HIGH_THRESHOLD,
    MIN_SURFACE,
    MODIFIERS,
    POSSIBLE_THRESHOLD,
    PROBABLE_THRESHOLD,
    composite_confidence,
    confidence_band,
)

# The exact table from SoW §6.2, restated here independently so the test fails
# loudly if anyone silently edits services.scoring.MODIFIERS.
EXPECTED_MODIFIERS: dict[str, tuple[float, str]] = {
    "same_zone": (+0.08, "Same zone ✓"),
    "adjacent_zone": (+0.04, "Adjacent zone ✓"),
    "same_venue": (+0.03, "Same venue ✓"),
    "different_venue": (-0.12, "⚠ Different venue"),
    "same_city": (+0.06, "Same city of origin ✓"),
    "same_state": (+0.03, "Same state ✓"),
    "temporal_very_recent": (+0.07, "Time gap under 2 hours ✓"),
    "temporal_same_day": (+0.04, "Same day ✓"),
    "temporal_stale": (-0.08, "⚠ Report over 3 days old"),
    "landmark_pattern_match": (+0.07, "Landmark pattern match ✓"),
    "language_match": (+0.04, "Language spoken matches ✓"),
    "possible_duplicate": (-0.05, "⚠ Possible duplicate report"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Modifier table integrity
# ─────────────────────────────────────────────────────────────────────────────
def test_modifier_table_matches_sow_exactly() -> None:
    assert MODIFIERS == EXPECTED_MODIFIERS


def test_modifier_keys_cover_scoreable_graph_signals() -> None:
    """Every modifier key is a GraphSignals field (so the matcher can set it)."""
    from schemas.match import GraphSignals

    signal_fields = set(GraphSignals.model_fields.keys())
    assert set(MODIFIERS.keys()) <= signal_fields


@pytest.mark.parametrize("signal,expected", list(EXPECTED_MODIFIERS.items()))
def test_each_modifier_delta_and_label(
    signal: str, expected: tuple[float, str]
) -> None:
    """Fire exactly one signal from a fixed base; verify its delta and label."""
    expected_delta, expected_label = expected
    base = 0.50
    score, reasons = composite_confidence(base, {signal: True})

    assert score == pytest.approx(round(base + expected_delta, 3))
    assert reasons == [expected_label]


# ─────────────────────────────────────────────────────────────────────────────
# composite_confidence — accumulation, ordering, defaults
# ─────────────────────────────────────────────────────────────────────────────
def test_no_signals_returns_base_unchanged() -> None:
    score, reasons = composite_confidence(0.732, {})
    assert score == 0.732
    assert reasons == []


def test_unknown_or_false_signals_are_ignored() -> None:
    score, reasons = composite_confidence(
        0.60,
        {"not_a_real_signal": True, "same_zone": False, "same_city": False},
    )
    assert score == 0.60
    assert reasons == []


def test_multiple_signals_accumulate() -> None:
    # 0.70 + same_zone(0.08) + same_city(0.06) + language_match(0.04) = 0.88
    signals = {"same_zone": True, "same_city": True, "language_match": True}
    score, reasons = composite_confidence(0.70, signals)
    assert score == pytest.approx(0.88)
    assert reasons == ["Same zone ✓", "Same city of origin ✓", "Language spoken matches ✓"]


def test_negative_modifiers_pull_score_down() -> None:
    # 0.80 + different_venue(-0.12) + temporal_stale(-0.08) = 0.60
    signals = {"different_venue": True, "temporal_stale": True}
    score, reasons = composite_confidence(0.80, signals)
    assert score == pytest.approx(0.60)
    assert reasons == ["⚠ Different venue", "⚠ Report over 3 days old"]


def test_reasons_follow_modifier_declaration_order() -> None:
    """Even if signals are passed out of order, labels read in MODIFIERS order."""
    signals = {
        "possible_duplicate": True,  # last in MODIFIERS
        "same_zone": True,  # first in MODIFIERS
        "temporal_same_day": True,  # middle
    }
    _, reasons = composite_confidence(0.65, signals)
    assert reasons == ["Same zone ✓", "Same day ✓", "⚠ Possible duplicate report"]


# ─────────────────────────────────────────────────────────────────────────────
# Clamping to [0, 1]
# ─────────────────────────────────────────────────────────────────────────────
def test_clamp_upper_bound() -> None:
    # 0.99 + same_zone(0.08) = 1.07 → clamped to 1.0
    score, _ = composite_confidence(0.99, {"same_zone": True})
    assert score == 1.0


def test_clamp_lower_bound() -> None:
    # 0.05 + different_venue(-0.12) = -0.07 → clamped to 0.0
    score, _ = composite_confidence(0.05, {"different_venue": True})
    assert score == 0.0


def test_clamp_does_not_drop_reasons() -> None:
    """Clamping affects the score, not which reasons fired."""
    _, reasons = composite_confidence(0.02, {"different_venue": True})
    assert reasons == ["⚠ Different venue"]


# ─────────────────────────────────────────────────────────────────────────────
# Rounding to 3 dp
# ─────────────────────────────────────────────────────────────────────────────
def test_result_is_rounded_to_three_dp() -> None:
    score, _ = composite_confidence(0.123456, {})
    assert score == 0.123


def test_rounding_with_modifier() -> None:
    # 0.777777 + same_venue(0.03) = 0.807777 → 0.808
    score, _ = composite_confidence(0.777777, {"same_venue": True})
    assert score == 0.808


def test_result_has_at_most_three_decimals() -> None:
    score, _ = composite_confidence(0.6666666, {"same_state": True})
    # round() guarantees ≤ 3 dp; assert via string form to be explicit.
    assert len(str(score).split(".")[-1]) <= 3


# ─────────────────────────────────────────────────────────────────────────────
# Band thresholds (SoW §6.3)
# ─────────────────────────────────────────────────────────────────────────────
def test_band_threshold_constants() -> None:
    assert HIGH_THRESHOLD == 0.90
    assert PROBABLE_THRESHOLD == 0.75
    assert POSSIBLE_THRESHOLD == 0.60
    assert MIN_SURFACE == 0.60


@pytest.mark.parametrize(
    "score,expected",
    [
        (1.0, ConfidenceBand.high),
        (0.95, ConfidenceBand.high),
        (0.90, ConfidenceBand.high),  # inclusive lower edge
        (0.8999, ConfidenceBand.probable),
        (0.80, ConfidenceBand.probable),
        (0.75, ConfidenceBand.probable),  # inclusive lower edge
        (0.7499, ConfidenceBand.possible),
        (0.65, ConfidenceBand.possible),
        (0.60, ConfidenceBand.possible),  # inclusive lower edge
        (0.5999, None),
        (0.50, None),
        (0.0, None),
    ],
)
def test_confidence_band_thresholds(score: float, expected: ConfidenceBand | None) -> None:
    assert confidence_band(score) == expected


def test_below_floor_is_none_not_a_band() -> None:
    """Sub-0.60 returns None (the matcher drops it), never a ConfidenceBand."""
    result = confidence_band(0.5)
    assert result is None
    assert not isinstance(result, ConfidenceBand)


def test_band_helper_is_consistent_with_composite() -> None:
    """End-to-end: a high-scoring combination lands in the 'high' band."""
    score, _ = composite_confidence(0.86, {"same_zone": True})  # → 0.94
    assert score == pytest.approx(0.94)
    assert confidence_band(score) is ConfidenceBand.high
