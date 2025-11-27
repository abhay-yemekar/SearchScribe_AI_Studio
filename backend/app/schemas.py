# backend/app/schemas.py
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr


# ---------- User / Auth ----------


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Content generation ----------


class ContentRequest(BaseModel):
    query: str


class RegenerateRequest(BaseModel):
    article: str
    style_instruction: str


class SEOResult(BaseModel):
    title: str
    description: str
    keywords: List[str]
    og_title: Optional[str] = None
    og_description: Optional[str] = None


class ContentResponse(BaseModel):
    article: str
    seo_metadata: Dict[str, Any]
    html: str


class ArticleHistoryOut(BaseModel):
    id: int
    query: str
    article: str
    seo_metadata: Dict[str, Any]
    html: str
    created_at: datetime

    class Config:
        orm_mode = True
