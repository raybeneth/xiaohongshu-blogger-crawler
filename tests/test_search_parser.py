from xiaohongshu_blogger_crawler.parsers.blogger_search_parser import parse_search_result


def test_parse_search_result_chooses_best_candidate() -> None:
    html_text = '''
    <script>
      {"userId":"wrong_001","nickname":"达人A官方","followerCount":"0.8w","noteCount":"10"}
      {"userId":"correct_999","nickname":"达人A","followerCount":"2.3w","noteCount":"88"}
    </script>
    '''

    result = parse_search_result(
        html_text=html_text,
        query_name="达人A",
        base_url="https://www.xiaohongshu.com",
    )

    assert result.blogger_id == "correct_999"
    assert result.matched_name == "达人A"
    assert result.followers == 23000
    assert result.notes == 88
    assert result.profile_url == "https://www.xiaohongshu.com/user/profile/correct_999"


def test_parse_search_result_returns_not_found_when_empty() -> None:
    result = parse_search_result(
        html_text="<html><body>empty</body></html>",
        query_name="达人B",
        base_url="https://www.xiaohongshu.com",
    )

    assert result.blogger_id is None
    assert result.matched_name is None
    assert result.is_found is False
