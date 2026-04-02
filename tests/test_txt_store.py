from pathlib import Path

from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult
from xiaohongshu_blogger_crawler.storage.txt_store import save_search_results_txt


def test_save_search_results_txt(tmp_path: Path) -> None:
    output_path = tmp_path / "result.txt"
    results = [
        BloggerSearchResult(
            query_name="达人A",
            matched_name="达人A",
            blogger_id="abc123",
            profile_url="https://www.xiaohongshu.com/user/profile/abc123",
            followers=1000,
            notes=12,
        ),
        BloggerSearchResult(query_name="达人B"),
    ]

    save_search_results_txt(results, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert "query_name=达人A" in content
    assert "status=FOUND" in content
    assert "query_name=达人B" in content
    assert "status=NOT_FOUND" in content
