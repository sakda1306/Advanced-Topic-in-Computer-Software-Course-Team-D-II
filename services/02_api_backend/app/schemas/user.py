"""User, login and preferences (CONTRACT.md §1)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.db import models
from app.schemas.common import Text

Role = Literal["user", "admin"]
Language = Literal["th", "en"]

# favorite_team_id is an INTEGER column.
MAX_INT32 = 2_147_483_647


class UserOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: Role
    favorite_team_id: int | None
    language: Language

    @classmethod
    def of(cls, user: models.User) -> UserOut:
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,  # type: ignore[arg-type]
            favorite_team_id=user.favorite_team_id,
            language=user.language,  # type: ignore[arg-type]
        )


class UserEnvelope(BaseModel):
    user: UserOut


class LoginRequest(BaseModel):
    username: Text = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PreferencesRequest(BaseModel):
    """Both fields are optional; a field that is sent (even null) is applied."""

    favorite_team_id: int | None = Field(default=None, ge=1, le=MAX_INT32)
    language: Language | None = None
