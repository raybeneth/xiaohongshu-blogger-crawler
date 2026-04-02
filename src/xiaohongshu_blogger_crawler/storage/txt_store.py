from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult


def init_search_results_txt(total: int, output_path: Path) -> None:
    """Create (or overwrite) the output file and write the header."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Xiaohongshu Blogger Search Results",
        f"generated_at_utc={datetime.now(timezone.utc).isoformat()}",
        f"total={total}",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def append_search_result_txt(item: BloggerSearchResult, index: int, output_path: Path) -> None:
    """Append a single result entry to an existing file."""
    lines: list[str] = [f"[{index}] query_name={item.query_name}"]
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
    with output_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def save_search_results_txt(results: Sequence[BloggerSearchResult], output_path: Path) -> None:
    init_search_results_txt(len(results), output_path)
    for index, item in enumerate(results, start=1):
        append_search_result_txt(item, index, output_path)


def _format_int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)
