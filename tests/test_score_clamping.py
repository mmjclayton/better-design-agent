"""Tests for the component-scorer clamping guard."""

from src.analysis.component_detector import ComponentScore


def test_score_clamped_below_zero():
    """Negative scores get clamped to 0."""
    c = ComponentScore(
        name="Forms", type="form", selector="form",
        score=-149, max_score=10,
    )
    assert c.score == 0


def test_score_clamped_above_max():
    """Scores above max_score get clamped to max_score."""
    c = ComponentScore(
        name="Forms", type="form", selector="form",
        score=50, max_score=10,
    )
    assert c.score == 10


def test_score_in_range_preserved():
    c = ComponentScore(
        name="Forms", type="form", selector="form",
        score=7, max_score=10,
    )
    assert c.score == 7


def test_zero_score_preserved():
    c = ComponentScore(
        name="Forms", type="form", selector="form",
        score=0, max_score=10,
    )
    assert c.score == 0


def test_max_score_preserved():
    c = ComponentScore(
        name="Forms", type="form", selector="form",
        score=10, max_score=10,
    )
    assert c.score == 10


def test_max_score_zero_clamps_score_to_zero():
    """max_score=0 edge case."""
    c = ComponentScore(
        name="Something", type="x", selector="x",
        score=5, max_score=0,
    )
    assert c.score == 0
