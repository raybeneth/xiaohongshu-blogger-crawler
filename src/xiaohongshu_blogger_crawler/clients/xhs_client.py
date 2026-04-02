from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from xiaohongshu_blogger_crawler.config import Settings

_RETRY_STOP: Final = stop_after_attempt(3)
_RETRY_WAIT: Final = wait_exponential(multiplier=1, min=1, max=8)


class XiaohongshuClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "XiaohongshuClient":
        headers = {
            "User-Agent": self._settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if self._settings.cookie:
            headers["Cookie"] = self._settings.cookie

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=self._settings.request_timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        _ = (exc_type, exc_value, traceback)
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("XiaohongshuClient must be used with 'async with'.")
        return self._client

    async def _wait_if_needed(self) -> None:
        if self._settings.request_interval_seconds > 0:
            await asyncio.sleep(self._settings.request_interval_seconds)

    @retry(
        reraise=True,
        stop=_RETRY_STOP,
        wait=_RETRY_WAIT,
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def _get_page(self, url: str) -> str:
        response = await self._require_client().get(url)
        response.raise_for_status()
        await self._wait_if_needed()
        return response.text

    async def fetch_profile_page(self, blogger_id: str) -> str:
        profile_url = self._settings.blogger_profile_url(blogger_id)
        return await self._get_page(profile_url)

    async def fetch_search_result_page(self, name: str) -> str:
        search_url = self._settings.search_result_url()
        request_param = {
            "search_user_request": {
                "biz_type": "web_search_user",
                "keyword": name,
                "page": 1,
                "page_size": 1,
                "request_id": "1636043819-1775119338742",
                "search_id": "2g6p35903w3icemm87sl1"
            }
        }
        return await self.post_blogger(search_url, request_param)

    @retry(
        reraise=True,
        stop=_RETRY_STOP,
        wait=_RETRY_WAIT,
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def post_blogger(self, url: str, request_param: dict) -> str:
        # x-t / x-s / x-s-common 三者联动，需同步从浏览器抓取后更新
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "origin": "https://www.xiaohongshu.com",
            "referer": "https://www.xiaohongshu.com/",
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            ),
            "x-b3-traceid": "c4f1e058822478c5",
            "x-t": self._settings.xt,
            "x-s": self._settings.xs,
            "x-s-common": self._settings.xs_common,
            "x-xray-traceid": "cea6b8efd0f9647ff31759787293f22b",
        }
        response = await self._require_client().post(url, json=request_param, headers=headers)
        response.raise_for_status()
        await self._wait_if_needed()
        # info
        logging.log(20,"接口返回信息 %s", response.text)
        return response.text
