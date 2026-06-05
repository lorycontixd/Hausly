import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    firebase_uid: str = Field(unique=True, index=True)
    display_name: str
    email: str
    avatar_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
