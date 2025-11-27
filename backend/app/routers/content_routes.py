# backend/app/routers/content_routes.py
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from .. import schemas, models
from ..llm_client import generate_article_with_html, regenerate_article_style

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/generate", response_model=schemas.ContentResponse)
def generate_content(
    payload: schemas.ContentRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Main generation flow:
    - Calls Gemini (via llm_client) to write article + SEO metadata + full HTML.
    - llm_client already handles all Gemini errors and falls back to local content.
    - Saves a history row in the database.
    """

    # llm_client.generate_article_with_html returns a dict.
    result = generate_article_with_html(payload.query)

    article_html = result.get("article", "")
    # key name in llm_client is "seo"
    seo_metadata = result.get("seo") or result.get("seo_metadata") or {}
    full_html = result.get("html", "")

    # Persist history
    history = models.ArticleHistory(
        user_id=current_user.id,
        query=payload.query,
        article=article_html,
        seo_metadata=json.dumps(seo_metadata),
        html=full_html,
    )
    db.add(history)
    db.commit()

    return schemas.ContentResponse(
        article=article_html,
        seo_metadata=seo_metadata,
        html=full_html,
    )


@router.post("/regenerate", response_model=schemas.ContentResponse)
def regenerate(
    payload: schemas.RegenerateRequest,
    current_user=Depends(get_current_user),
):
    """
    Regeneration API:
    - Takes the existing article HTML and a style instruction.
    - Uses llm_client.regenerate_article_style to rewrite the article.
    - Returns the updated article + a simple HTML wrapper.
    - llm_client handles LLM errors and falls back to the original article.
    """

    regen_result = regenerate_article_style(
        payload.article, payload.style_instruction
    )

    # regen_result is a dict from llm_client; be defensive in case of future changes
    if isinstance(regen_result, dict):
        updated_article = regen_result.get("article", "") or payload.article
    else:
        updated_article = str(regen_result or payload.article)

    # Minimal SEO; you can make this richer if you want
    seo_metadata = {
        "title": "Regenerated Article",
        "description": f"Article regenerated in style: {payload.style_instruction}",
    }

    full_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{seo_metadata["title"]}</title>
  <meta name="description" content="{seo_metadata["description"]}">
</head>
<body>
  {updated_article}
</body>
</html>
""".strip()

    return schemas.ContentResponse(
        article=updated_article,
        seo_metadata=seo_metadata,
        html=full_html,
    )


@router.get("/history", response_model=list[schemas.ArticleHistoryOut])
def get_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return recent generated articles (with SEO + HTML) for the current user.
    Ordered by newest first.
    """
    query = (
        db.query(models.ArticleHistory)
        .filter(models.ArticleHistory.user_id == current_user.id)
        .order_by(models.ArticleHistory.created_at.desc())
        .limit(limit)
    )

    rows = query.all()
    items: list[schemas.ArticleHistoryOut] = []

    for row in rows:
        try:
            seo_meta = json.loads(row.seo_metadata) if row.seo_metadata else {}
        except json.JSONDecodeError:
            seo_meta = {}

        items.append(
            schemas.ArticleHistoryOut(
                id=row.id,
                query=row.query,
                article=row.article,
                seo_metadata=seo_meta,
                html=row.html,
                created_at=row.created_at,
            )
        )

    return items
