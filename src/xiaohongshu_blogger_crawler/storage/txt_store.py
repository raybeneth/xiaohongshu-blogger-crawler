from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult


def save_search_results_txt(results: Sequence[BloggerSearchResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Xiaohongshu Blogger Search Results",
        f"generated_at_utc={datetime.now(timezone.utc).isoformat()}",
        f"total={len(results)}",
        "",
    ]

    for index, item in enumerate(results, start=1):
        lines.append(f"[{index}] query_name={item.query_name}")
        if item.is_found:
            lines.append("status=FOUND")
            lines.append(f"matched_name={item.matched_name or ''}")
            lines.append(f"red_id={item.red_id or ''}")
            lines.append(f"blogger_id={item.blogger_id or ''}")
            lines.append(f"profile_url={item.profile_url or ''}")
            lines.append(f"avatar_url={item.avatar_url or ''}")
            lines.append(f"followers={_format_int(item.followers)}")
            lines.append(f"notes={_format_int(item.notes)}")
            lines.append(f"profession={item.profession or ''}")
            lines.append(f"official_verified={item.official_verified if item.official_verified is not None else ''}")
            lines.append(f"update_time={item.update_time or ''}")
        else:
            lines.append("status=NOT_FOUND")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _format_int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)
