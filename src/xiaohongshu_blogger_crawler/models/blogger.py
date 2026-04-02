from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class BloggerProfile(BaseModel):
    blogger_id: str
    profile_url: str
    nickname: str | None = None
    followers: int | None = None
    following: int | None = None
    likes_and_collects: int | None = Field(default=None, alias="likesAndCollects")
    source: str = "xiaohongshu"
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
