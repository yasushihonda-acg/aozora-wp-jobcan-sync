"""CLI tests for `render` and `list` subcommands.

Phase 2A.1b — exercises `python -m sync list --category-id <cid> --fixture <path>`
plus exit-code paths (input validation, structure change, render).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sync.cli import app

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "jobcan_responses"
runner = CliRunner()


class TestListSubcommand:
    def test_renders_listing_to_stdout(self) -> None:
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(FIXTURES_DIR / "list_care.html"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "<!DOCTYPE html>" in result.stdout
        assert "求人一覧" in result.stdout
        assert "job-list-card" in result.stdout

    def test_writes_to_out_file(self, tmp_path: Path) -> None:
        out = tmp_path / "list.html"
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(FIXTURES_DIR / "list_office.html"),
                "--out",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.is_file()
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")
        # The stderr summary mentions the byte count and item count
        assert "wrote" in result.output
        assert "10 jobs" in result.output

    @pytest.mark.parametrize("bad", ["18773a", "abc", "1８7７3"])  # full-width digits
    def test_rejects_non_ascii_digits(self, bad: str) -> None:
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                bad,
                "--fixture",
                str(FIXTURES_DIR / "list_care.html"),
            ],
        )
        assert result.exit_code == 1
        assert "category_id must be ASCII digits" in result.output

    def test_structure_change_exit_code(self, tmp_path: Path) -> None:
        """An HTML file with zero `.job-offer-box` exits with code 2."""
        broken = tmp_path / "empty.html"
        broken.write_text("<html><body><p>no cards here</p></body></html>")
        result = runner.invoke(
            app,
            [
                "list",
                "--category-id",
                "18773",
                "--fixture",
                str(broken),
            ],
        )
        assert result.exit_code == 2
        assert "structure-change" in result.output


class TestRenderSubcommandStillWorks:
    """Regression guard: adding `list` must not break the existing `render` flow."""

    def test_render_fixture(self) -> None:
        result = runner.invoke(
            app,
            [
                "render",
                "1777023",
                "--fixture",
                str(FIXTURES_DIR / "job_1777023.html"),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "<!DOCTYPE html>" in result.stdout
        assert "job-detail__title" in result.stdout
