from __future__ import annotations

import logging

import aiomysql

from xiaohongshu_blogger_crawler.dashboard.database import get_pool
from xiaohongshu_blogger_crawler.dashboard.models import BrandSubscription

logger = logging.getLogger(__name__)

_COLUMNS = (
    "id, state, group_id, brand_id, contract_code, counselor, versions, status, "
    "contract_start_time, contract_end_time, data_start_time, data_end_time, "
    "sampling_proportion, xhs_register_status, create_time, update_time"
)

_COLUMN_NAMES = [c.strip() for c in _COLUMNS.split(",")]


def _row_to_model(row: tuple) -> BrandSubscription:
    return BrandSubscription(**dict(zip(_COLUMN_NAMES, row)))


async def list_subscriptions() -> list[BrandSubscription]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_COLUMNS} FROM redpan_brand_subscription ORDER BY id DESC"
            )
            rows = await cur.fetchall()
    return [_row_to_model(r) for r in rows]


async def get_subscription(sub_id: int) -> BrandSubscription | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_COLUMNS} FROM redpan_brand_subscription WHERE id = %s",
                (sub_id,),
            )
            row = await cur.fetchone()
    return _row_to_model(row) if row else None
