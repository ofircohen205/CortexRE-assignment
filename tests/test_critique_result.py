"""Verify CritiqueResult dataclass fields and approved property."""
from src.services.llm.service import CritiqueResult


def test_approved_true_when_score_at_threshold():
    result = CritiqueResult(
        scores={"accuracy": 8, "completeness": 8, "clarity": 8, "format": 8},
        weighted_total=80,
        issues=[],
        revised_answer=None,
    )
    assert result.approved is True


def test_approved_false_when_score_below_threshold():
    result = CritiqueResult(
        scores={"accuracy": 5, "completeness": 5, "clarity": 5, "format": 5},
        weighted_total=50,
        issues=["Revenue figure wrong."],
        revised_answer="Fixed answer.",
    )
    assert result.approved is False


def test_formatting_only_defaults_false():
    result = CritiqueResult(
        scores={"accuracy": 6, "completeness": 6, "clarity": 6, "format": 3},
        weighted_total=57,
        issues=["bad format"],
        revised_answer="fixed",
    )
    assert result.formatting_only is False


def test_formatting_only_can_be_true():
    result = CritiqueResult(
        scores={"accuracy": 9, "completeness": 9, "clarity": 9, "format": 5},
        weighted_total=90,
        issues=["Contains currency symbol '$'."],
        revised_answer="The answer is 100,000.00.",
        formatting_only=True,
    )
    assert result.formatting_only is True


def test_weighted_total_stored():
    result = CritiqueResult(
        scores={"accuracy": 10, "completeness": 10, "clarity": 10, "format": 10},
        weighted_total=100,
        issues=[],
        revised_answer=None,
    )
    assert result.weighted_total == 100
