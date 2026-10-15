"""Deterministic HTML rendering.

The LLM never emits HTML. It returns structured article JSON; this module
renders it through an autoescaped Jinja2 template, so output is safe by
construction (sanitizer runs afterwards as defense in depth).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from jinja2 import Environment, StrictUndefined, select_autoescape

from .schemas import GeneratedArticle, SeoResult

if TYPE_CHECKING:
    from ..schemas.media import ArticlePhoto
from .validation import DESCRIPTION_MAX, TITLE_MAX, _truncate, fitting_first_sentence

_env = Environment(
    autoescape=select_autoescape(default=True), trim_blocks=True, undefined=StrictUndefined
)

ARTICLE_PAGE_TEMPLATE = _env.from_string(
    """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ seo.title }}</title>
  <meta name="description" content="{{ seo.description }}">
  <meta name="keywords" content="{{ seo.keywords | join(', ') }}">
  <meta property="og:title" content="{{ seo.og_title or seo.title }}">
  <meta property="og:description" content="{{ seo.og_description or seo.description }}">
  <meta name="robots" content="{{ seo.robots }}">
  {% if seo.canonical_url %}<link rel="canonical" href="{{ seo.canonical_url }}">{% endif %}
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.65;
           max-width: 46rem; margin: 0 auto; padding: 2rem 1.25rem; color: #1a202c; }
    h1 { font-size: 2rem; line-height: 1.2; }
    h2 { margin-top: 2rem; }
    .intro { font-size: 1.1rem; color: #4a5568; }
    .conclusion { border-top: 1px solid #e2e8f0; margin-top: 2.5rem; padding-top: 1rem; }
    figure { margin: 1.5rem 0; }
    figure img { display: block; width: 100%; height: auto; border-radius: .5rem; }
    figcaption { margin-top: .5rem; font-size: .75rem; color: #52616a; overflow-wrap: anywhere; }
  </style>
</head>
<body>
  {% macro photo_figure(photo) %}
  <figure>
    <img src="{{ photo.preview_url }}" alt="{{ photo.alt }}" width="{{ photo.width }}"
         height="{{ photo.height }}" loading="lazy" decoding="async" referrerpolicy="no-referrer">
    <figcaption>{{ photo.title }} —
      <a href="{{ photo.source_url }}" rel="noopener noreferrer">{{ photo.creator }}</a>,
      <a href="{{ photo.license_url }}" rel="noopener noreferrer">{{ photo.license_name }}</a>.
      Wikimedia Commons.</figcaption>
  </figure>
  {% endmacro %}
  <article>
    <h1>{{ article.title }}</h1>
    {% for photo in photos %}
    {% if photo.section_id is none %}{{ photo_figure(photo) }}{% endif %}
    {% endfor %}
    <p class="intro">{{ article.introduction }}</p>
    {% for section in article.sections %}
    <section>
      <h2>{{ section.heading }}</h2>
      {% for photo in photos %}
      {% if photo.section_id == section.id %}{{ photo_figure(photo) }}{% endif %}
      {% endfor %}
      {% for paragraph in section.paragraphs %}
      <p>{{ paragraph }}</p>
      {% endfor %}
      {% if section.bullets %}
      <ul>
        {% for bullet in section.bullets %}
        <li>{{ bullet }}</li>
        {% endfor %}
      </ul>
      {% endif %}
    </section>
    {% endfor %}
    <p class="conclusion">{{ article.conclusion }}</p>
    <section>
      {% if article.research.status == "sources_retrieved" %}
      <h2>Sources</h2>
      <p>Sources retrieved: {{ article.research.retrieved_at }}.
         Review claims before publishing; retrieved sources are not a fact-check guarantee.</p>
      <ul>{% for source in article.research.sources %}
        <li>[{{ source.id }}] <a href="{{ source.url }}">{{ source.title }}</a>
          {% if source.published_at %} — reported publication/update:
          {{ source.published_at }} (provider estimate){% endif %}</li>
      {% endfor %}</ul>
      {% else %}
      <p>Unresearched draft: no live sources were retrieved.
         Verify factual and time-sensitive claims before publishing.</p>
      {% endif %}
    </section>
  </article>
</body>
</html>
"""
)


def _fallback_seo(article: GeneratedArticle) -> SeoResult:
    """Keep existing article wording, visibly pending review; never canned copy."""
    passages = [article.introduction]
    for section in article.sections:
        passages.extend(section.paragraphs)
    passages.append(article.conclusion)
    description = next(
        (sentence for passage in passages if (sentence := fitting_first_sentence(
            re.sub(r"\[S\d+(?:,\s*S\d+)*\]", "", passage)
        )) is not None),
        _truncate(article.title, DESCRIPTION_MAX),
    )
    # Titles/headings are useful editable seeds; extraction is not keyword research.
    keywords = list(dict.fromkeys(
        _truncate(text, 80).lower()
        for text in [article.title, *[section.heading for section in article.sections]]
    ))[:5]
    return SeoResult(
        title=_truncate(article.title, TITLE_MAX), description=description,
        keywords=keywords, og_title=_truncate(article.title, TITLE_MAX),
        og_description=description, review_status="needs_review",
    )


def render_article_html(
    article: GeneratedArticle, seo: SeoResult | None = None,
    *, photos: list[ArticlePhoto] | None = None,
) -> str:
    """Render a complete standalone HTML page for the article."""
    return ARTICLE_PAGE_TEMPLATE.render(
        article=article, seo=seo or _fallback_seo(article), photos=photos or []
    )
