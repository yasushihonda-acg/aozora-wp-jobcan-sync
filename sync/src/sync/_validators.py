"""Shared input validators used by both the CLI and the FastAPI proxy.

Phase 2A.3 cleanup (code-review finding #4): the ASCII-digit check lived
inline in three places — cli.py:render, cli.py:list_, and app.py:_is_valid_id
— each with its own copy of the explanatory comment. Consolidating here
means the rule lives in one file and the comment doesn't drift between
copies as the rule evolves.
"""

from __future__ import annotations


def is_ascii_digit_id(value: str) -> bool:
    """Return True only for ASCII-digit-only strings.

    `str.isdigit()` alone accepts full-width '１２３' and Arabic-Indic digits,
    which Jobcan rejects with 404 and obscures the encoding root cause from
    the operator. Pairing it with `.isascii()` keeps the input contract
    aligned with what Jobcan actually parses.
    """
    return value.isascii() and value.isdigit()
