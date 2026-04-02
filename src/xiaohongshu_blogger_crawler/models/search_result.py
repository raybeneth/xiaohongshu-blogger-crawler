from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class BloggerSearchResult(BaseModel):
    query_name: str
    matched_name: str | None = None
    blogger_id: str | None = None
    red_id: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    followers: int | None = None
    notes: int | None = None
    profession: str | None = None
    official_verified: bool | None = None
    update_time: str | None = None
    source: str = "xiaohongshu_search_page"
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_found(self) -> bool:
        return self.blogger_id is not None
