from __future__ import annotations

import logging
import os

import aiomysql

logger = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None

DB_HOST = os.getenv("DASHBOARD_DB_HOST", "")
DB_PORT = int(os.getenv("DASHBOARD_DB_PORT", "3306"))
DB_NAME = os.getenv("DASHBOARD_DB_NAME", "")
DB_USER = os.getenv("DASHBOARD_DB_USER", "")
DB_PASSWORD = os.getenv("DASHBOARD_DB_PASSWORD", "")


async def init_pool() -> None:
    global _pool
    _pool = await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        db=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
        minsize=1,
        maxsize=5,
    )
    logger.info("MySQL pool created (%s:%s/%s)", DB_HOST, DB_PORT, DB_NAME)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("MySQL pool closed")


def get_pool() -> aiomysql.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool
