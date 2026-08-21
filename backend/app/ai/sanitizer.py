"""HTML sanitization via nh3 (Rust ammonia bindings).

Defense in depth: renderer output is already autoescaped, but anything that
is persisted or handed to a browser passes through here too.
"""

from __future__ import annotations

import nh3

# Document structure + content tags we legitimately produce in rendered pages.
ALLOWED_TAGS = {
    "html", "head", "body", "title", "meta", "link", "style",
    "article", "section", "p", "span", "div",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "strong", "em", "b", "i", "u",
    "a", "code", "pre", "br", "hr", "table", "thead", "tbody", "tr", "th", "td",
}

ALLOWED_ATTRIBUTES = {
    "meta": {"charset", "name", "content", "property"},
    # link_rel is None so <link rel="canonical"> survives; renderer emits no
    # <a> tags, and sanitizer tests assert dangerous schemes never do.
    "link": {"rel", "href"},
    "a": {"href", "title", "rel"},
    "*": {"class"},
}


def sanitize_html(html: str) -> str:
    """Strip scripts, event handlers, and javascript: URLs from an HTML fragment."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel=None,
        strip_comments=True,
        url_schemes={"http", "https", "mailto"},
        # nh3 scrubs <style>/<script> content by default; we keep our
        # renderer's benign <style> block, everything else is still rejected.
        clean_content_tags=set(),
    )


def sanitize_document(page: str) -> str:
    """Sanitize a full rendered article page, preserving document structure.

    nh3 is fragment-oriented (it drops <html>/<head>/<body> wrappers), so we
    split the page at our renderer's fixed skeleton: the <head> holds only
    template-generated tags (autoescaped attributes), and the body content is
    sanitized as a fragment before reassembly.
    """
    head_end = page.find("</head>")
    body_open = page.find("<body>")
    body_close = page.rfind("</body>")
    if -1 in (head_end, body_open, body_close) or not (
        head_end < body_open < body_close
    ):
        # Not our document shape; fall back to whole-input fragment cleaning.
        return sanitize_html(page)

    head = page[: head_end + len("</head>")]
    body_inner = page[body_open + len("<body>") : body_close]
    return f"{head}<body>{sanitize_html(body_inner)}</body></html>"
