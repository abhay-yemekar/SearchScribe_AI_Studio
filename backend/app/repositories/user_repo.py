"""Data access for users and their refresh-token sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.base import utc_now
from ..db.models import RefreshToken, User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def create(self, *, email: str, name: str, password_hash: str) -> User:
        user = User(email=email, name=name, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def touch_last_login(self, user: User) -> None:
        user.last_login_at = utc_now()
        self.db.commit()

    def create_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(token)
        self.db.commit()
        return token

    def find_refresh_token(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )

    def revoke_refresh_token(self, token: RefreshToken) -> None:
        token.revoked_at = utc_now()
        self.db.commit()

    def revoke_all_refresh_tokens(self, user_id: int) -> None:
        self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
            .values(revoked_at=utc_now())
        )
        self.db.commit()
