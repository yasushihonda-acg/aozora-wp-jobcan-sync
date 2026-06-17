"""AC-5: design tokens consistency.

Phase 0 evaluator + Codex (Phase 2A) flagged that the sync templates reference
`var(--foo)` tokens that live in `mockup/assets/css/tokens.css`. If that file
ever renames a token (e.g. `--color-accent` -> `--color-primary`), the sync CSS
silently fails (browsers treat undefined CSS variables as empty fallback).

This test scans every CSS file under `sync/` (and `mockup/assets/css/sync-*.css`,
which sync-side templates link to) for `var(--token-name)` references, then
verifies each referenced token is defined in `mockup/assets/css/tokens.css`.

Failure means either tokens.css renamed a variable, or a sync-side CSS uses a
typo'd name. Either way, a human needs to look.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# __file__ = aozora-wp-jobcan-sync/sync/tests/test_design_tokens.py
#   parents[0] = sync/tests, parents[1] = sync, parents[2] = aozora-wp-jobcan-sync
REPO_ROOT = Path(__file__).resolve().parents[2]
TOKENS_CSS = REPO_ROOT / "mockup" / "assets" / "css" / "tokens.css"

# Sync-side CSS files that reference tokens.css variables.
SYNC_CSS_DIRS = [
    REPO_ROOT / "mockup" / "assets" / "css",  # sync-job-detail.css and any future sync-*.css
]
SYNC_CSS_PATTERNS = ["sync-*.css"]


def _extract_var_references(css_text: str) -> set[str]:
    """Find every `var(--name)` reference in the CSS."""
    return set(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)", css_text))


def _extract_var_definitions(css_text: str) -> set[str]:
    """Find every `--name:` token definition in tokens.css."""
    return set(re.findall(r"^\s*(--[a-zA-Z0-9_-]+)\s*:", css_text, flags=re.MULTILINE))


def _gather_sync_css_files() -> list[Path]:
    files: list[Path] = []
    for d in SYNC_CSS_DIRS:
        if not d.is_dir():
            continue
        for pattern in SYNC_CSS_PATTERNS:
            files.extend(d.glob(pattern))
    return sorted(files)


@pytest.fixture(scope="module")
def defined_tokens() -> set[str]:
    assert TOKENS_CSS.is_file(), f"tokens.css missing: {TOKENS_CSS}"
    return _extract_var_definitions(TOKENS_CSS.read_text(encoding="utf-8"))


def test_at_least_one_sync_css_file_exists() -> None:
    """Sanity guard so the test below doesn't pass vacuously."""
    files = _gather_sync_css_files()
    assert files, "no sync-*.css files found — has the sync renderer been removed?"


def test_every_sync_css_var_reference_is_defined_in_tokens(defined_tokens: set[str]) -> None:
    """Every `var(--token)` in sync CSS must be defined in tokens.css.

    AC-5 of Phase 2A. If this fails:
      - check whether tokens.css renamed a variable
      - or whether the sync CSS has a typo (e.g. --colour-accent vs --color-accent)
    """
    missing: dict[str, set[str]] = {}
    for css_file in _gather_sync_css_files():
        used = _extract_var_references(css_file.read_text(encoding="utf-8"))
        undefined = used - defined_tokens
        if undefined:
            missing[css_file.name] = undefined
    assert not missing, (
        "sync CSS references CSS variables that are not defined in mockup/assets/css/tokens.css.\n"
        "Update tokens.css or fix the variable names in the sync CSS files below:\n"
        + "\n".join(f"  {name}: {sorted(vars_)}" for name, vars_ in missing.items())
    )
