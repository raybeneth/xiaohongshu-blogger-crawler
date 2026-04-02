from __future__ import annotations

import json
from pathlib import Path

from xiaohongshu_blogger_crawler.models.blogger import BloggerProfile


def save_profile(profile: BloggerProfile, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = profile.model_dump(mode="json", by_alias=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
