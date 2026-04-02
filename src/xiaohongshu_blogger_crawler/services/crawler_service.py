from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from xiaohongshu_blogger_crawler.clients.xhs_client import XiaohongshuClient
from xiaohongshu_blogger_crawler.config import Settings, settings
from xiaohongshu_blogger_crawler.models.blogger import BloggerProfile
from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult
from xiaohongshu_blogger_crawler.parsers.blogger_parser import parse_blogger_profile
from xiaohongshu_blogger_crawler.parsers.blogger_search_parser import parse_search_result_from_api
from xiaohongshu_blogger_crawler.storage.json_store import save_profile
from xiaohongshu_blogger_crawler.storage.txt_store import (
    append_search_result_txt,
    init_search_results_txt,
    save_search_results_txt,
)

LOGGER = logging.getLogger(__name__)


class CrawlerService:
    def __init__(self, cfg: Settings = settings) -> None:
        self._settings = cfg

    async def crawl_blogger(self, blogger_id: str, output: Path | None = None) -> BloggerProfile:
        profile_url = self._settings.blogger_profile_url(blogger_id)

        async with XiaohongshuClient(self._settings) as client:
            html_text = await client.fetch_profile_page(blogger_id)

        profile = parse_blogger_profile(
            html_text=html_text,
            blogger_id=blogger_id,
            profile_url=profile_url,
        )

        output_path = output if output is not None else self._default_output_path(blogger_id)
        save_profile(profile, output_path)
        LOGGER.info("Profile saved: %s", output_path.as_posix())
        return profile

    async def crawl_bloggers_by_names_to_txt(
        self,
        names: Sequence[str] | None = None,
        output: Path | None = None,
    ) -> tuple[Path, list[BloggerSearchResult]]:
        target_names = self._sanitize_names(names if names is not None else self._settings.blogger_names)
        if not target_names:
            raise ValueError("No blogger names provided. Set XHS_BLOGGER_NAMES or pass --name options.")

        if not self._settings.cookie:
            raise ValueError("XHS_COOKIE is empty. Set your account cookie before crawling.")

        output_path = output if output is not None else self._timestamped_output_path()
        init_search_results_txt(len(target_names), output_path)
        LOGGER.info("Output file initialised: %s", output_path.as_posix())

        results: list[BloggerSearchResult] = []
        async with XiaohongshuClient(self._settings) as client:
            for index, name in enumerate(target_names, start=1):
                html_text = await client.fetch_search_result_page(name)
                parsed = parse_search_result_from_api(
                    json_text=html_text,
                    query_name=name,
                    base_url=self._settings.base_url,
                )
                results.append(parsed)
                append_search_result_txt(parsed, index, output_path)
                LOGGER.info(
                    "[%d/%d] '%s': %s — written to %s",
                    index, len(target_names), name,
                    "FOUND" if parsed.is_found else "NOT_FOUND",
                    output_path.as_posix(),
                )

                if index < len(target_names):
                    if index % self._settings.batch_pause_every == 0:
                        pause = random.uniform(
                            self._settings.batch_pause_min,
                            self._settings.batch_pause_max,
                        )
                        LOGGER.info("Batch pause after %d queries: %.1fs", index, pause)
                        await asyncio.sleep(pause)
                    else:
                        wait = random.uniform(
                            self._settings.query_interval_min,
                            self._settings.query_interval_max,
                        )
                        LOGGER.info("Query interval: %.1fs", wait)
                        await asyncio.sleep(wait)

        return output_path, results

    async def search_by_name(self, name: str) -> BloggerSearchResult:
        """Search one blogger by nickname and return the result without saving to file."""
        if not self._settings.cookie:
            raise ValueError("XHS_COOKIE is empty. Set your account cookie before crawling.")

        async with XiaohongshuClient(self._settings) as client:
            html_text = await client.fetch_search_result_page(name)

        result = parse_search_result_from_api(
            json_text=html_text,
            query_name=name,
            base_url=self._settings.base_url,
        )
        LOGGER.info("Search completed for '%s': %s", name, "FOUND" if result.is_found else "NOT_FOUND")
        return result

    def _timestamped_output_path(self) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        stem = Path(self._settings.batch_txt_filename).stem
        return self._settings.output_dir / f"{stem}_{ts}.txt"

    def _default_output_path(self, blogger_id: str) -> Path:
        return self._settings.output_dir / f"{blogger_id}.json"

    @staticmethod
    def _sanitize_names(names: Sequence[str]) -> list[str]:
        sanitized: list[str] = []
        seen: set[str] = set()
        for raw in names:
            name = raw.strip()
            if not name or name in seen:
                continue
            sanitized.append(name)
            seen.add(name)
        return sanitized
