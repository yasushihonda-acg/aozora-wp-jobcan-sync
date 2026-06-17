"""Selector / synonym / sanitise configuration loaded from YAML.

Codex review (Phase 2A) reflected:
- `ConfigError` is distinct from `JobcanStructureChangeError`. The latter means
  "Jobcan changed their HTML"; the former means "we shipped a broken config".
- The YAML is validated at startup via Pydantic; a malformed file fails fast
  instead of producing confusing runtime errors deep in the parser.
- Synonyms are explicit lists, not fuzzy match. `給与例 -> 給与` would be a
  legal-content mismatch and is dangerous; the parser leaves unknown headers
  in `extra_lines` instead.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from .models import JobcanError


class ConfigError(JobcanError):
    """Raised when `selectors.yaml` is missing or fails Pydantic validation."""


class DetailSelectors(BaseModel):
    title: str
    body: str
    address: str
    label: str
    apply_link: str
    table_lines: str
    table_header: str
    table_body: str


class RequiredTableField(BaseModel):
    canonical: str = Field(..., min_length=1)
    synonyms: list[str] = Field(..., min_length=1)

    @field_validator("synonyms")
    @classmethod
    def _canonical_must_be_in_synonyms(cls, v: list[str], info: object) -> list[str]:
        # The canonical name must also appear in synonyms so the match step
        # doesn't need a special case for "exact canonical match".
        #
        # NOTE: This validator runs per-field, and Pydantic v2 populates
        # `info.data` in declaration order. Because `canonical` is declared
        # before `synonyms` in `RequiredTableField`, `info.data["canonical"]`
        # is reliably available here.
        #
        # WARNING: If the field declaration order is ever swapped (or this
        # field's check is moved to a sibling model), the `except` branch
        # below will silently skip validation. Phase 2A.2 may migrate to
        # `model_validator(mode="after")` for stronger guarantees.
        try:
            canonical = info.data["canonical"]  # type: ignore[attr-defined]
        except (AttributeError, KeyError):
            return v
        if canonical not in v:
            raise ValueError(f"canonical {canonical!r} must appear in synonyms list")
        return v


class DetailConfig(BaseModel):
    selectors: DetailSelectors
    required_table_fields: dict[str, RequiredTableField]


class ListSelectors(BaseModel):
    job_card: str
    job_url: str
    title: str
    address: str
    label: str
    description: str


class ListConfig(BaseModel):
    selectors: ListSelectors


class SanitizeConfig(BaseModel):
    allowed_tags: list[str] = Field(..., min_length=1)
    drop_tags: list[str] = Field(..., min_length=1)


class SelectorConfig(BaseModel):
    version: int = Field(..., ge=1)
    detail: DetailConfig
    list: ListConfig
    sanitize: SanitizeConfig

    model_config = {"frozen": True}


DEFAULT_CONFIG_PATH = Path(__file__).parent / "selectors.yaml"


def load_selector_config(path: Path | None = None) -> SelectorConfig:
    """Load and validate `selectors.yaml`.

    Raises:
        ConfigError: file missing, invalid YAML, or fails Pydantic schema.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(f"selectors config not found: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"selectors config not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"selectors config must be a mapping at the top level: {config_path}")
    try:
        return SelectorConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"selectors config failed validation: {exc}") from exc


@lru_cache(maxsize=1)
def default_config() -> SelectorConfig:
    """Memoised default config — load once per process."""
    return load_selector_config()
