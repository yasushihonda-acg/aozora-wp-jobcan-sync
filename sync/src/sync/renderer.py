"""Jinja2 renderer for the in-house job-detail and job-list templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import JobListPage, JobOffer

TEMPLATES_DIR = Path(__file__).parent / "templates"


def make_environment(templates_dir: Path | None = None) -> Environment:
    """Build a Jinja2 environment with autoescape enabled for HTML output."""
    loader = FileSystemLoader(str(templates_dir or TEMPLATES_DIR))
    return Environment(
        loader=loader,
        autoescape=select_autoescape(["html", "xml"]),
        keep_trailing_newline=True,
    )


def render_job_detail(job: JobOffer, *, env: Environment | None = None) -> str:
    """Render a single job offer into HTML using `job_detail.html`."""
    env = env or make_environment()
    template = env.get_template("job_detail.html")
    return template.render(job=job, page_title=job.page_title)


def render_job_list(page: JobListPage, *, env: Environment | None = None) -> str:
    """Render a parsed Jobcan listing page into HTML using `job_list.html`."""
    env = env or make_environment()
    template = env.get_template("job_list.html")
    return template.render(page=page)
