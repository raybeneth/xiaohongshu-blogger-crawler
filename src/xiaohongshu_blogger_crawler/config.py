from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _parse_blogger_names(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()

    cleaned = raw_value.strip()
    if not cleaned:
        return ()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        tokens = [token.strip() for token in cleaned.replace("\n", ",").split(",")]
        return tuple(token for token in tokens if token)

    if not isinstance(parsed, list):
        return ()

    names: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        name = str(item).strip()
        if not name or name in seen:
            continue
        names.append(name)
        seen.add(name)

    return tuple(names)


@dataclass(slots=True, frozen=True)
class Settings:
    base_url: str = os.getenv("XHS_BASE_URL", "https://www.xiaohongshu.com")
    search_url: str = os.getenv("XHS_SEARCH_URL", "https://edith.xiaohongshu.com")
    xt: str = os.getenv("XHS_XT", "")
    xs: str = os.getenv("XHS_XS", "")
    xs_common: str = os.getenv("XHS_XS_COMMON", "")
    user_agent: str = os.getenv(
        "XHS_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    )
    cookie: str = os.getenv("XHS_COOKIE", "").strip()
    request_timeout: float = float(os.getenv("XHS_REQUEST_TIMEOUT", "15"))
    request_interval_seconds: float = float(os.getenv("XHS_REQUEST_INTERVAL_SECONDS", "1.5"))
    output_dir: Path = Path(os.getenv("XHS_OUTPUT_DIR", "data"))
    blogger_names: tuple[str, ...] = field(
        default_factory=lambda: _parse_blogger_names(os.getenv("XHS_BLOGGER_NAMES"))
    )
    search_source: str = os.getenv("XHS_SEARCH_SOURCE", "web_explore_feed")
    batch_txt_filename: str = os.getenv("XHS_BATCH_TXT_FILENAME", "blogger_search_results.txt")

    def blogger_profile_url(self, blogger_id: str) -> str:
        clean_id = blogger_id.strip()
        return f"{self.base_url.rstrip('/')}/user/profile/{clean_id}"

    def search_result_url(self) -> str:
        base = self.search_url.rstrip("/")
        search_url = f"{base}/api/sns/web/v1/search/usersearch"
        logging.info("Search result url: %s", search_url)
        return search_url

    def batch_output_path(self) -> Path:
        return self.output_dir / self.batch_txt_filename


settings = Settings()
