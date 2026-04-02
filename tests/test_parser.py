from xiaohongshu_blogger_crawler.parsers.blogger_parser import parse_blogger_profile


def test_parse_profile_from_html_payload() -> None:
    html_text = '''
    <html>
      <head><title>demo_user - xiaohongshu</title></head>
      <body>
        <script>
          {"nickname":"demo_user","followerCount":"1.2w","followingCount":80,"likesAndCollects":"3.5w"}
        </script>
      </body>
    </html>
    '''

    profile = parse_blogger_profile(
        html_text=html_text,
        blogger_id="abc123",
        profile_url="https://www.xiaohongshu.com/user/profile/abc123",
    )

    assert profile.nickname == "demo_user"
    assert profile.followers == 12000
    assert profile.following == 80
    assert profile.likes_and_collects == 35000
