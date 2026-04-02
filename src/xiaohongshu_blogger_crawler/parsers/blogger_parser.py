from __future__ import annotations

import html
import re

from xiaohongshu_blogger_crawler.models.blogger import BloggerProfile

_NICKNAME_PATTERNS = (
    r'"nickname"\s*:\s*"(?P<value>[^"]+)"',
    r'"nickName"\s*:\s*"(?P<value>[^"]+)"',
    r"<title>(?P<value>[^<]+)</title>",
)
_FOLLOWERS_PATTERNS = (
    r'"followerCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"fans"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
)
_FOLLOWING_PATTERNS = (
    r'"followingCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"follows"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
)
_LIKES_PATTERNS = (
    r'"likesAndCollects"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"likedCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
)


def parse_blogger_profile(html_text: str, blogger_id: str, profile_url: str) -> BloggerProfile:
    nickname = _extract_string(html_text, _NICKNAME_PATTERNS)
    followers = _extract_int(html_text, _FOLLOWERS_PATTERNS)
    following = _extract_int(html_text, _FOLLOWING_PATTERNS)
    likes_and_collects = _extract_int(html_text, _LIKES_PATTERNS)

    return BloggerProfile(
        blogger_id=blogger_id,
        profile_url=profile_url,
        nickname=nickname,
        followers=followers,
        following=following,
        likesAndCollects=likes_and_collects,
    )


def _extract_string(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue

        raw_value = match.group("value").strip()
        decoded = html.unescape(raw_value)
        if "\\u" in decoded:
            try:
                decoded = bytes(decoded, "utf-8").decode("unicode_escape")
            except UnicodeDecodeError:
                pass

        cleaned = decoded.replace("- xiaohongshu", "").strip()
        if cleaned:
            return cleaned

    return None


def _extract_int(text: str, patterns: tuple[str, ...]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue

        parsed_value = _parse_number(match.group("value"))
        if parsed_value is not None:
            return parsed_value

    return None


def _parse_number(value: str) -> int | None:
    raw = value.strip().replace(",", "").replace(" ", "")
    if not raw:
        return None

    multiplier = 1
    if raw.endswith(("w", "W", "万")):
        multiplier = 10_000
        raw = raw[:-1]

    try:
        number = float(raw)
    except ValueError:
        return None

    return int(number * multiplier)
