"""Versioned prompt registry.

Prompts live as files under app/ai/prompts/ and are registered with an
(name, version) key. Generation metadata records both, making AI behavior
reproducible and debuggable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, StrictUndefined

PROMPTS_DIR = Path(__file__).parent

# (name, version) -> file inside PROMPTS_DIR
_REGISTRY: dict[tuple[str, str], str] = {
    ("article_generation", "v1"): "article_generation_v1.md",
    ("seo_generation", "v1"): "seo_generation_v1.md",
    ("rewrite", "v1"): "rewrite_v1.md",
}

_env = Environment(
    autoescape=False,  # noqa: S701 - plain-text model input, never rendered as HTML
    undefined=StrictUndefined,
    keep_trailing_newline=False,
)


class UnknownPromptError(KeyError):
    pass


@lru_cache(maxsize=64)
def _load(name: str, version: str) -> str:
    try:
        filename = _REGISTRY[(name, version)]
    except KeyError:
        raise UnknownPromptError(f"prompt {name}/{version} is not registered") from None
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def render_prompt(name: str, version: str, variables: dict[str, str]) -> str:
    """Load and render a registered prompt. Unknown variables raise."""
    template = _env.from_string(_load(name, version))
    return template.render(**variables)


def available_prompts() -> list[tuple[str, str]]:
    return sorted(_REGISTRY)
