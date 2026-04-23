from __future__ import annotations

import logging

import aiomysql

from xiaohongshu_blogger_crawler.dashboard.database import get_pool
from xiaohongshu_blogger_crawler.dashboard.models import BrandSubscription, CleanTaskProgress, SysConfig

logger = logging.getLogger(__name__)

_SUB_COLUMNS = (
    "s.id, s.state, s.group_id, s.brand_id, s.contract_code, s.counselor, "
    "s.versions, s.status, s.contract_start_time, s.contract_end_time, "
    "s.data_start_time, s.data_end_time, s.sampling_proportion, "
    "s.xhs_register_status, s.create_time, s.update_time, "
    "e.brand_name, e.doris_url, e.doris_account, e.doris_password"
)

_COLUMN_NAMES = [c.strip().split(".")[-1] for c in _SUB_COLUMNS.split(",")]


def _row_to_model(row: tuple) -> BrandSubscription:
    return BrandSubscription(**dict(zip(_COLUMN_NAMES, row)))


async def list_subscriptions() -> list[BrandSubscription]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_SUB_COLUMNS} "
                "FROM redpan_brand_subscription s "
                "LEFT JOIN redpan_brand_ext e ON s.group_id = e.group_id AND s.brand_id = e.brand_id "
                "ORDER BY s.id DESC"
            )
            rows = await cur.fetchall()
    return [_row_to_model(r) for r in rows]


async def advance_subscription_status(sub_id: int) -> BrandSubscription | None:
    """将订阅状态推进一步：1→2，2→3。其他状态不处理。"""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_SUB_COLUMNS} "
                "FROM redpan_brand_subscription s "
                "LEFT JOIN redpan_brand_ext e ON s.group_id = e.group_id AND s.brand_id = e.brand_id "
                "WHERE s.id = %s",
                (sub_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None
            sub = _row_to_model(row)
            if sub.status not in (1, 2):
                logger.warning("订阅 %d 当前状态 %d，不允许推进", sub_id, sub.status)
                return sub
            new_status = sub.status + 1
            await cur.execute(
                "UPDATE redpan_brand_subscription SET status = %s WHERE id = %s",
                (new_status, sub_id),
            )
            logger.info("订阅 %d 状态从 %d 推进到 %d", sub_id, sub.status, new_status)
            sub.status = new_status
            return sub


async def create_contract(data: dict) -> None:
    """
    新增合约：在一个事务中向 7 张表写入数据。

    data 字段说明见 plan 中的 Form Fields → Table Mapping。
    """
    pool = get_pool()
    group_id = int(data["group_id"])
    brand_id = int(data["brand_id"])

    # doris_url 存储为 JDBC 格式
    doris_host = data["doris_url"].strip().rstrip("/")
    doris_db = data.get("doris_database", "").strip()
    doris_url = (
        f"jdbc:mysql://{doris_host}:9030/{doris_db}"
        "?characterEncoding=utf-8&zeroDateTimeBehavior=convertToNull"
        "&useSSL=false&allowMultiQueries=true&useOldAliasMetadataBehavior=true"
    )

    async with pool.acquire() as conn:
        conn: aiomysql.Connection
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                # 1. redpan_group 可能会触发唯一键重复
                await cur.execute(
                    "INSERT IGNORE INTO redpan_group (group_id, group_name, ma_doris_database) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE group_name=VALUES(group_name), "
                    "ma_doris_database=VALUES(ma_doris_database)",
                    (group_id, data.get("group_name", ""), data.get("ma_doris_database", "")),
                )

                # 2. redpan_brand
                await cur.execute(
                    "INSERT INTO redpan_brand (group_id, brand_id, auth_code) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE auth_code=VALUES(auth_code)",
                    (group_id, brand_id, data.get("auth_code", "")),
                )

                # 3. redpan_brand_auth_record
                await cur.execute(
                    "INSERT INTO redpan_brand_auth_record (group_id, brand_id) "
                    "VALUES (%s, %s)",
                    (group_id, brand_id),
                )

                # 4. redpan_brand_ext
                await cur.execute(
                    "INSERT INTO redpan_brand_ext "
                    "(group_id, brand_id, brand_name, brand_version, view_id, "
                    " doris_url, doris_account, doris_password) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "brand_name=VALUES(brand_name), brand_version=VALUES(brand_version), "
                    "view_id=VALUES(view_id), doris_url=VALUES(doris_url), "
                    "doris_account=VALUES(doris_account), doris_password=VALUES(doris_password)",
                    (
                        group_id, brand_id,
                        data.get("brand_name", ""),
                        data.get("brand_version", "STAND"),
                        data.get("view_id", ""),
                        doris_url,
                        data.get("doris_account", ""),
                        data.get("doris_password", ""),
                    ),
                )

                # 5. redpan_xhs_config
                await cur.execute(
                    "INSERT INTO redpan_xhs_config (group_id, brand_id, xhs_brand_id) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE xhs_brand_id=VALUES(xhs_brand_id)",
                    (group_id, brand_id, int(data.get("xhs_brand_id", 0))),
                )

                # 6. redpan_data_mpc_config
                await cur.execute(
                    "INSERT INTO redpan_data_mpc_config "
                    "(group_id, brand_id, use_code, secret, busi_config_name, "
                    " busi_config_id, hive_database) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "use_code=VALUES(use_code), secret=VALUES(secret), "
                    "busi_config_name=VALUES(busi_config_name), "
                    "busi_config_id=VALUES(busi_config_id), "
                    "hive_database=VALUES(hive_database)",
                    (
                        group_id, brand_id,
                        data.get("use_code", ""),
                        data.get("mpc_secret", ""),
                        data.get("busi_config_name", ""),
                        data.get("busi_config_id", ""),
                        data.get("hive_database", ""),
                    ),
                )

                # 7. redpan_brand_subscription
                await cur.execute(
                    "INSERT INTO redpan_brand_subscription "
                    "(group_id, brand_id, contract_code, counselor, counselor_mobile, "
                    " versions, status, contract_start_time, contract_end_time, "
                    " data_start_time, data_end_time, sampling_proportion) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s)",
                    (
                        group_id, brand_id,
                        data.get("contract_code", ""),
                        data.get("counselor", ""),
                        data.get("counselor_mobile", ""),
                        int(data.get("versions", 0)),
                        data["contract_start_time"],
                        data["contract_end_time"],
                        data["data_start_time"],
                        data["data_end_time"],
                        int(data.get("sampling_proportion", 100)),
                    ),
                )

            await conn.commit()
            logger.info("新增合约成功: group_id=%s, brand_id=%s", group_id, brand_id)
        except Exception:
            await conn.rollback()
            logger.exception("新增合约失败，已回滚: group_id=%s, brand_id=%s", group_id, brand_id)
            raise


async def get_subscription(sub_id: int) -> BrandSubscription | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_SUB_COLUMNS} "
                "FROM redpan_brand_subscription s "
                "LEFT JOIN redpan_brand_ext e ON s.group_id = e.group_id AND s.brand_id = e.brand_id "
                "WHERE s.id = %s",
                (sub_id,),
            )
            row = await cur.fetchone()
    return _row_to_model(row) if row else None


# ── SysConfig CRUD ─────────────────────────────────────────────────────────

_SC_COLUMNS = "id, state, create_time, update_time, code, value, type, remark, encryption"
_SC_NAMES = [c.strip() for c in _SC_COLUMNS.split(",")]


def _row_to_sys_config(row: tuple) -> SysConfig:
    return SysConfig(**dict(zip(_SC_NAMES, row)))


async def list_sys_configs() -> list[SysConfig]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_SC_COLUMNS} FROM redpan_sys_config WHERE state = 1 ORDER BY id DESC"
            )
            rows = await cur.fetchall()
    return [_row_to_sys_config(r) for r in rows]


async def create_sys_config(data: dict) -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO redpan_sys_config (code, value, type, remark, encryption) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    data["code"],
                    data["value"],
                    int(data.get("type", 0)),
                    data.get("remark", ""),
                    data.get("encryption", ""),
                ),
            )
            new_id = cur.lastrowid
    logger.info("新增系统配置: id=%s, code=%s", new_id, data["code"])
    return new_id


async def update_sys_config(config_id: int, data: dict) -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE redpan_sys_config SET code=%s, value=%s, type=%s, remark=%s, encryption=%s "
                "WHERE id=%s AND state=1",
                (
                    data["code"],
                    data["value"],
                    int(data.get("type", 0)),
                    data.get("remark", ""),
                    data.get("encryption", ""),
                    config_id,
                ),
            )
            affected = cur.rowcount
    logger.info("更新系统配置: id=%s, affected=%s", config_id, affected)
    return affected > 0


async def delete_sys_config(config_id: int) -> bool:
    """逻辑删除：将 state 设为 0。"""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE redpan_sys_config SET state=0 WHERE id=%s AND state=1",
                (config_id,),
            )
            affected = cur.rowcount
    logger.info("逻辑删除系统配置: id=%s, affected=%s", config_id, affected)
    return affected > 0


# ── CleanTaskProgress ──────────────────────────────────────────────────────

_CT_COLUMNS = (
    "t.id, t.state, t.create_time, t.update_time, t.code, "
    "t.group_id, t.brand_id, t.status, t.progress, t.fail_cause, "
    "e.brand_name"
)
_CT_NAMES = [c.strip().split(".")[-1] for c in _CT_COLUMNS.split(",")]


def _row_to_clean_task(row: tuple) -> CleanTaskProgress:
    return CleanTaskProgress(**dict(zip(_CT_NAMES, row)))


async def list_clean_task_progress() -> list[CleanTaskProgress]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {_CT_COLUMNS} "
                "FROM redpan_data_clean_task_progress t "
                "LEFT JOIN redpan_brand_ext e ON t.group_id = e.group_id AND t.brand_id = e.brand_id "
                "WHERE t.state = 1 "
                "ORDER BY t.update_time DESC"
            )
            rows = await cur.fetchall()
    return [_row_to_clean_task(r) for r in rows]


async def retry_clean_task(task_id: int) -> bool:
    """将失败的清洗任务重置为待执行（status=0）。"""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE redpan_data_clean_task_progress SET status=0, fail_cause=NULL "
                "WHERE id=%s AND status=3 AND state=1",
                (task_id,),
            )
            affected = cur.rowcount
    logger.info("重试清洗任务: id=%s, affected=%s", task_id, affected)
    return affected > 0
