"""Deterministic HTML rendering.

The LLM never emits HTML. It returns structured article JSON; this module
renders it through an autoescaped Jinja2 template, so output is safe by
construction (sanitizer runs afterwards as defense in depth).
"""

from __future__ import annotations

from jinja2 import Environment, StrictUndefined, select_autoescape

from .schemas import GeneratedArticle, SeoResult

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
  </style>
</head>
<body>
  <article>
    <h1>{{ article.title }}</h1>
    <p class="intro">{{ article.introduction }}</p>
    {% for section in article.sections %}
    <section>
      <h2>{{ section.heading }}</h2>
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
  </article>
</body>
</html>
"""
)


def _fallback_seo(article: GeneratedArticle) -> SeoResult:
    """Deterministic metadata when SEO generation is unavailable."""
    description = article.introduction[:160]
    first_word = article.title.split()[0] if article.title.split() else "article"
    return SeoResult(
        title=article.title[:60],
        description=description,
        keywords=[first_word],
    )


def render_article_html(article: GeneratedArticle, seo: SeoResult | None = None) -> str:
    """Render a complete standalone HTML page for the article."""
    return ARTICLE_PAGE_TEMPLATE.render(
        article=article, seo=seo or _fallback_seo(article)
    )
