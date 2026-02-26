"""Verify CritiqueResult dataclass has the formatting_only field."""
from src.services.llm.service import CritiqueResult


def test_critique_result_formatting_only_defaults_false():
    result = CritiqueResult(approved=False, issues=["bad format"], revised_answer="fixed")
    assert result.formatting_only is False


def test_critique_result_formatting_only_can_be_true():
    result = CritiqueResult(
        approved=False,
        issues=["Contains currency symbol '$'."],
        revised_answer="The answer is 100,000.00.",
        formatting_only=True,
    )
    assert result.formatting_only is True
