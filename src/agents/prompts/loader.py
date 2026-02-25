"""
agents/prompts/loader.py
========================
Utility for reading markdown prompt files at runtime.

Why markdown files?
-------------------
Storing prompts as ``.md`` files separates content from code:
  - Prompt engineers can edit language / structure without touching Python.
  - Git diffs on prompts are clean, human-readable text diffs.
  - Prompts can be previewed directly in any markdown viewer.

Usage::

    from src.agents.prompts.loader import load_prompt

    system_prompt = load_prompt("intent")                        # intent.md
    extractor_prompt = load_prompt("extractor", property_list=...)  # with template vars
"""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: str) -> str:
    """
    Load a prompt from a markdown file and apply optional template substitutions.

    Parameters
    ----------
    name:
        Filename stem of the prompt (without ``.md``), e.g. ``"intent"``,
        ``"extractor"``, or ``"responder"``.
    **kwargs:
        Named placeholders to substitute in the template.  For example,
        ``load_prompt("extractor", property_list="- Building A\\n- 123 Main St")``
        replaces ``{property_list}`` in ``extractor.md``.

    Returns
    -------
    str
        The full prompt text, with any ``{key}`` placeholders replaced.

    Raises
    ------
    FileNotFoundError
        If no ``.md`` file with the given name exists in the prompts directory.
    KeyError
        If the template contains a ``{placeholder}`` that was not supplied.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file '{path}' not found.  "
            f"Available prompts: {[p.stem for p in _PROMPTS_DIR.glob('*.md')]}"
        )

    text = path.read_text(encoding="utf-8")

    if kwargs:
        text = text.format(**kwargs)

    return text
