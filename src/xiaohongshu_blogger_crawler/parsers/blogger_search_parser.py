from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult

_CARD_PATTERN = re.compile(
    r"\{[^{}]{0,1200}\"(?:userId|user_id)\"\s*:\s*\"?[^\"]+\"?[^{}]{0,1800}\}",
    re.IGNORECASE,
)

_NAME_PATTERNS = (
    r'"nickname"\s*:\s*"(?P<value>[^"]+)"',
    r'"nickName"\s*:\s*"(?P<value>[^"]+)"',
    r'"name"\s*:\s*"(?P<value>[^"]+)"',
)
_ID_PATTERNS = (
    r'"userId"\s*:\s*"(?P<value>[^"]+)"',
    r'"user_id"\s*:\s*"?(?P<value>[\w\-]+)"?',
)
_FOLLOWERS_PATTERNS = (
    r'"followerCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"fans"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"fansCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
)
_NOTES_PATTERNS = (
    r'"noteCount"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
    r'"notes"\s*:\s*"?(?P<value>[\d.,]+(?:[wW万])?)"?',
)


@dataclass(slots=True)
class _Candidate:
    blogger_id: str | None
    matched_name: str | None
    followers: int | None
    notes: int | None


def parse_search_result_from_api(json_text: str, query_name: str, base_url: str) -> BloggerSearchResult:
    """Parse the JSON response returned by the XHS search API."""
    try:
        data = json.loads(json_text)
        users = data.get("data", {}).get("users") or []
    except (json.JSONDecodeError, AttributeError):
        return BloggerSearchResult(query_name=query_name)

    if not users:
        return BloggerSearchResult(query_name=query_name)

    user = users[0]
    blogger_id: str | None = user.get("id") or None
    matched_name: str | None = user.get("name") or None
    followers = _parse_number(str(user.get("fans", "")))
    notes_raw = user.get("note_count")
    notes = int(notes_raw) if notes_raw is not None else None

    profile_url = (
        f"{base_url.rstrip('/')}/user/profile/{blogger_id}" if blogger_id else None
    )
    return BloggerSearchResult(
        query_name=query_name,
        matched_name=matched_name,
        blogger_id=blogger_id,
        red_id=user.get("red_id") or None,
        profile_url=profile_url,
        avatar_url=user.get("image") or None,
        followers=followers,
        notes=notes,
        profession=user.get("profession") or None,
        official_verified=user.get("red_official_verified"),
        update_time=user.get("update_time") or None,
    )


def parse_search_result(html_text: str, query_name: str, base_url: str) -> BloggerSearchResult:
    candidates = _extract_candidates(html_text)
    best = _select_best_candidate(query_name, candidates)

    if best is None or best.blogger_id is None:
        return BloggerSearchResult(query_name=query_name)

    profile_url = f"{base_url.rstrip('/')}/user/profile/{best.blogger_id}"
    return BloggerSearchResult(
        query_name=query_name,
        matched_name=best.matched_name,
        blogger_id=best.blogger_id,
        profile_url=profile_url,
        followers=best.followers,
        notes=best.notes,
    )


def _extract_candidates(html_text: str) -> list[_Candidate]:
    decoded_text = html.unescape(html_text)
    normalized_text = decoded_text.replace('\\"', '"')

    candidates: list[_Candidate] = []
    seen_keys: set[tuple[str | None, str | None]] = set()

    for match in _CARD_PATTERN.finditer(normalized_text):
        fragment = match.group(0)
        blogger_id = _extract_string(fragment, _ID_PATTERNS)
        matched_name = _extract_string(fragment, _NAME_PATTERNS)

        if blogger_id is None and matched_name is None:
            continue

        dedupe_key = (blogger_id, matched_name)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        followers = _extract_int(fragment, _FOLLOWERS_PATTERNS)
        notes = _extract_int(fragment, _NOTES_PATTERNS)
        candidates.append(
            _Candidate(
                blogger_id=blogger_id,
                matched_name=matched_name,
                followers=followers,
                notes=notes,
            )
        )

    return candidates


def _select_best_candidate(query_name: str, candidates: list[_Candidate]) -> _Candidate | None:
    if not candidates:
        return None

    query_norm = _normalize_text(query_name)
    ranked = sorted(
        candidates,
        key=lambda item: _candidate_score(query_norm, item),
        reverse=True,
    )
    return ranked[0]


def _candidate_score(query_norm: str, candidate: _Candidate) -> int:
    score = 0
    name_norm = _normalize_text(candidate.matched_name)

    if name_norm and name_norm == query_norm:
        score += 100
    elif name_norm and (query_norm in name_norm or name_norm in query_norm):
        score += 60

    if candidate.blogger_id:
        score += 30
    if candidate.followers is not None:
        score += min(candidate.followers // 1000, 20)

    return score


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", value).lower()


def _extract_string(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue

        value = match.group("value").strip()
        if value:
            return value

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
        raw = raw[:-1]
        multiplier = 10_000

    try:
        parsed = float(raw)
    except ValueError:
        return None

    return int(parsed * multiplier)
