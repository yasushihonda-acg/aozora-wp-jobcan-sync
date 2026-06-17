"""Phase 0 CLI: `python -m sync render <job_id>`.

Exit codes:
    0 — success (HTML rendered to stdout or --out file)
    1 — Jobcan client error (network / HTTP failure)
    2 — JobcanStructureChangeError (selectors missing)
    3 — JobcanValidationError (selectors found but required fields empty)
    4 — Render/template error
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from .jobcan_client import JobcanClient
from .models import JobcanClientError, JobcanStructureChangeError, JobcanValidationError
from .parser import parse_job_detail
from .renderer import render_job_detail

app = typer.Typer(
    add_completion=False,
    help="Aozora Phase B (Phase 0) — Jobcan proxy + in-house template renderer.",
    no_args_is_help=True,
)

_JOB_ID_ARG = typer.Argument(..., help="Jobcan job_offer ID (digits only)")
_OUT_OPT = typer.Option(None, "--out", "-o", help="Write HTML to this path (default: stdout)")
_FIXTURE_OPT = typer.Option(
    None,
    "--fixture",
    "-f",
    help="Read HTML from a local fixture file instead of fetching from Jobcan",
)


@app.command()
def render(
    job_id: str = _JOB_ID_ARG,
    out: Path | None = _OUT_OPT,
    fixture: Path | None = _FIXTURE_OPT,
) -> None:
    """Fetch and render a single job offer."""
    # Use ASCII-only digit check; `str.isdigit()` accepts full-width '１２３'
    # and Arabic-Indic digits, which Jobcan rejects with 404 and obscures the
    # encoding root cause from the operator.
    if not (job_id.isascii() and job_id.isdigit()):
        typer.echo(f"job_id must be ASCII digits, got: {job_id!r}", err=True)
        raise typer.Exit(code=1)

    try:
        if fixture is not None:
            html = fixture.read_text(encoding="utf-8")
            source_url = (
                f"https://recruit.jobcan.jp/aozora/job_offers/{job_id}"
                "?hide_breadcrumb=true&hide_search=true"
            )
        else:
            with JobcanClient() as client:
                source_url, html = client.fetch_job_detail(job_id)
    except JobcanClientError as exc:
        typer.echo(f"client error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        offer = parse_job_detail(html, source_url, job_id=job_id)
    except JobcanStructureChangeError as exc:
        typer.echo(f"structure-change: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except JobcanValidationError as exc:
        typer.echo(f"validation: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    try:
        rendered = render_job_detail(offer)
    except Exception as exc:
        typer.echo(f"render error: {exc}", err=True)
        raise typer.Exit(code=4) from exc

    if out is not None:
        out.write_text(rendered, encoding="utf-8")
        typer.echo(f"wrote {out} ({len(rendered)} bytes)", err=True)
    else:
        sys.stdout.write(rendered)


@app.command()
def version() -> None:
    """Print the package version."""
    from importlib.metadata import version as _v

    try:
        typer.echo(_v("aozora-sync"))
    except Exception:
        typer.echo("0.1.0 (unreleased)")


if __name__ == "__main__":
    app()
