from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from uuid import uuid4

HISTORY_FILE = Path("history.json")


class GenerationRecord(BaseModel):
    id: str
    created_at: str          # ISO timestamp
    kind: Literal["article", "seo"]
    prompt: str
    data: Dict[str, Any]


def _load_raw() -> List[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save_raw(rows: List[dict]) -> None:
    HISTORY_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def add_record(kind: str, prompt: str, data: Dict[str, Any]) -> GenerationRecord:
    rows = _load_raw()
    rec = GenerationRecord(
        id=str(uuid4()),
        created_at=datetime.utcnow().isoformat() + "Z",
        kind=kind,  # "article" or "seo"
        prompt=prompt,
        data=data,
    )
    rows.append(rec.dict())
    _save_raw(rows)
    return rec


def get_recent(limit: int = 20, kind: str | None = None) -> List[GenerationRecord]:
    rows = _load_raw()
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    rows = sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)
    rows = rows[:limit]
    return [GenerationRecord(**r) for r in rows]
