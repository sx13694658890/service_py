from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    created_at: datetime
    roles: list[str]


class CurrentUserOut(BaseModel):
    user_id: uuid.UUID
    email: str
    roles: list[str]


class UserListResponse(BaseModel):
    current_user: CurrentUserOut
    users: list[UserListItemOut]
    total: int = Field(..., ge=0)
