from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from xiaohongshu_blogger_crawler.dashboard.database import close_pool, init_pool
from fastapi import Request

from xiaohongshu_blogger_crawler.dashboard.task_manager import (
    advance_subscription_status,
    create_contract,
    create_sys_config,
    delete_sys_config,
    list_clean_task_progress,
    retry_clean_task,
    list_subscriptions,
    list_sys_configs,
    update_sys_config,
)

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR / "static"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="部署调度管理", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_DASH_USER = os.getenv("DASHBOARD_USERNAME", "admin")
_DASH_PASS = os.getenv("DASHBOARD_PASSWORD", "admin")
_SESSION_TTL = 3600  # 1 hour

# token -> expiry timestamp
_sessions: dict[str, float] = {}

_LOGIN_HTML = (_TEMPLATES_DIR / "login.html").read_text(encoding="utf-8") \
    if (_TEMPLATES_DIR / "login.html").exists() else ""

_PUBLIC_PATHS = {"/login", "/api/login", "/api/logout"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 静态资源和登录页放行
    if path.startswith("/static") or path in _PUBLIC_PATHS:
        return await call_next(request)

    token = request.cookies.get("dash_token", "")
    if token and token in _sessions and _sessions[token] > time.time():
        return await call_next(request)

    # token 过期则清理
    if token in _sessions:
        del _sessions[token]

    # API 请求返回 401 JSON
    if path.startswith("/api/"):
        return JSONResponse({"ok": False, "msg": "未登录或会话已过期"}, status_code=401)
    # 页面请求重定向到登录页
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page() -> HTMLResponse:
    return HTMLResponse(content=_LOGIN_HTML)


@app.post("/api/login")
async def api_login(request: Request) -> JSONResponse:
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")
    if username == _DASH_USER and password == _DASH_PASS:
        token = secrets.token_hex(32)
        _sessions[token] = time.time() + _SESSION_TTL
        resp = JSONResponse({"ok": True})
        resp.set_cookie("dash_token", token, max_age=_SESSION_TTL, httponly=True, samesite="lax")
        return resp
    return JSONResponse({"ok": False, "msg": "账号或密码错误"})


@app.post("/api/logout")
async def api_logout(request: Request) -> JSONResponse:
    token = request.cookies.get("dash_token", "")
    if token in _sessions:
        del _sessions[token]
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("dash_token")
    return resp


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    html = (_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/subscriptions")
async def api_list_subscriptions() -> list[dict]:
    subs = await list_subscriptions()
    return [s.model_dump(mode="json") for s in subs]


@app.post("/api/subscriptions/{sub_id}/advance")
async def api_advance_status(sub_id: int) -> dict:
    sub = await advance_subscription_status(sub_id)
    if sub is None:
        return {"ok": False, "msg": "订阅不存在"}
    return {"ok": True, "data": sub.model_dump(mode="json")}


@app.post("/api/contracts")
async def api_create_contract(request: Request) -> dict:
    data = await request.json()
    try:
        await create_contract(data)
    except Exception as exc:
        logger.exception("新增合约接口异常")
        return {"ok": False, "msg": str(exc)}
    return {"ok": True}


def _parse_jdbc_url(jdbc_url: str) -> tuple[str, int, str]:
    """从 JDBC URL 中提取 host, port, db。

    格式: jdbc:mysql://host:port/db?params...
    也兼容非 JDBC 格式: host:port/db 或 host/db
    """
    import re

    url = jdbc_url.strip()
    # 去掉 jdbc:mysql:// 前缀
    url = re.sub(r"^jdbc:mysql://", "", url)
    # 去掉查询参数
    url = url.split("?")[0]

    host, port, db = url, 9030, ""
    if "/" in host:
        host, db = host.split("/", 1)
    if ":" in host:
        host, port_str = host.split(":", 1)
        port = int(port_str)
    return host, port, db


def _des_decrypt(cipher_hex: str, key: str = "kedao888") -> str:
    """DES/CBC/PKCS5Padding 解密（hex 编码密文，IV = key）。"""
    from pyDes import CBC, PAD_PKCS5, des

    key_bytes = key.encode("utf-8")
    cipher_bytes = bytes.fromhex(cipher_hex)
    k = des(key_bytes, CBC, key_bytes, padmode=PAD_PKCS5)
    return k.decrypt(cipher_bytes).decode("utf-8")


_ALLOWED_SQL_PREFIXES = {"select", "insert", "update", "delete", "show", "explain"}

_PRIVILEGED_PASSWORD = os.getenv("SCRIPT_PRIVILEGED_PASSWORD", "")


def _is_safe_sql(statements: list[str]) -> bool:
    """检查所有语句是否都属于 SELECT/INSERT/UPDATE/DELETE。"""
    for stmt in statements:
        first_word = stmt.split()[0].lower() if stmt.split() else ""
        if first_word not in _ALLOWED_SQL_PREFIXES:
            return False
    return True


@app.post("/api/scripts/execute")
async def api_execute_script(request: Request) -> dict:
    """按品牌 Doris 数据源执行 SQL 脚本。"""
    import traceback

    import aiomysql

    data = await request.json()
    brand_id = int(data.get("brand_id", 0))
    sql_text: str = data.get("sql", "").strip()
    doris_url: str = data.get("doris_url", "")
    doris_account: str = data.get("doris_account", "")
    doris_password: str = data.get("doris_password", "")
    privileged_password: str = data.get("privileged_password", "")

    if not sql_text:
        return {"ok": False, "msg": "SQL 脚本为空"}
    if not doris_url or not doris_account:
        return {"ok": False, "msg": "品牌数据源信息不完整，请检查 Doris 配置"}

    # 解析 JDBC URL
    host, port, db = _parse_jdbc_url(doris_url)

    # DES 解密密码
    try:
        password = _des_decrypt(doris_password)
    except Exception:
        logger.warning("Doris 密码解密失败，尝试使用原文")
        password = doris_password

    # 拆分多条语句
    statements = [s.strip() for s in sql_text.split(";") if s.strip()]

    # 高危语句拦截
    if not _is_safe_sql(statements):
        if not privileged_password:
            return {"ok": False, "need_privilege": True, "msg": "检测到高危语句，需要高权限密码验证"}
        if not _PRIVILEGED_PASSWORD:
            return {"ok": False, "msg": "服务端未配置高权限密码（SCRIPT_PRIVILEGED_PASSWORD），无法执行"}
        if privileged_password != _PRIVILEGED_PASSWORD:
            return {"ok": False, "msg": "高权限密码错误"}

    conn = None
    try:
        conn = await aiomysql.connect(
            host=host,
            port=port,
            db=db,
            user=doris_account,
            password=password,
            charset="utf8mb4",
            connect_timeout=10,
        )
        all_results = []
        async with conn.cursor() as cur:
            for i, stmt in enumerate(statements):
                await cur.execute(stmt)
                if cur.description:
                    columns = [col[0] for col in cur.description]
                    rows = await cur.fetchall()
                    all_results.append({
                        "index": i + 1,
                        "sql": stmt[:200],
                        "columns": columns,
                        "rows": [list(r) for r in rows],
                        "row_count": len(rows),
                    })
                else:
                    all_results.append({
                        "index": i + 1,
                        "sql": stmt[:200],
                        "affected_rows": cur.rowcount,
                    })

        return {"ok": True, "results": all_results}

    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception("脚本执行失败: brand_id=%s", brand_id)
        return {"ok": False, "msg": str(exc), "traceback": tb}
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# SysConfig API
# ---------------------------------------------------------------------------

@app.get("/api/sys_configs")
async def api_list_sys_configs() -> list[dict]:
    configs = await list_sys_configs()
    return [c.model_dump(mode="json") for c in configs]


@app.post("/api/sys_configs")
async def api_create_sys_config(request: Request) -> dict:
    data = await request.json()
    try:
        new_id = await create_sys_config(data)
    except Exception as exc:
        logger.exception("新增系统配置异常")
        return {"ok": False, "msg": str(exc)}
    return {"ok": True, "id": new_id}


@app.put("/api/sys_configs/{config_id}")
async def api_update_sys_config(config_id: int, request: Request) -> dict:
    data = await request.json()
    try:
        ok = await update_sys_config(config_id, data)
    except Exception as exc:
        logger.exception("更新系统配置异常")
        return {"ok": False, "msg": str(exc)}
    return {"ok": ok, "msg": "" if ok else "记录不存在或已删除"}


@app.delete("/api/sys_configs/{config_id}")
async def api_delete_sys_config(config_id: int) -> dict:
    ok = await delete_sys_config(config_id)
    return {"ok": ok, "msg": "" if ok else "记录不存在或已删除"}


# ---------------------------------------------------------------------------
# CleanTaskProgress API
# ---------------------------------------------------------------------------

@app.get("/api/clean_tasks")
async def api_list_clean_tasks() -> list[dict]:
    tasks = await list_clean_task_progress()
    return [t.model_dump(mode="json") for t in tasks]


@app.post("/api/clean_tasks/{task_id}/retry")
async def api_retry_clean_task(task_id: int) -> dict:
    ok = await retry_clean_task(task_id)
    return {"ok": ok, "msg": "" if ok else "任务不存在或当前状态非失败"}


# ---------------------------------------------------------------------------
# Parquet Parser API
# ---------------------------------------------------------------------------

_MAX_PARQUET_SIZE = 30 * 1024 * 1024  # 30 MB


@app.post("/api/parquet/parse")
async def api_parse_parquet(file: UploadFile) -> dict:
    """解析上传的 Parquet 文件，返回列信息和行数据。"""
    import io
    import traceback

    import pyarrow.parquet as pq

    if not file.filename or not file.filename.endswith(".parquet"):
        return {"ok": False, "msg": "请上传 .parquet 文件"}

    content = await file.read()
    if len(content) > _MAX_PARQUET_SIZE:
        return {"ok": False, "msg": f"文件大小 {len(content) / 1024 / 1024:.1f}MB 超过 30MB 限制"}

    try:
        table = pq.read_table(io.BytesIO(content))
        columns = [field.name for field in table.schema]
        total_rows = table.num_rows
        # 最多返回前 500 行避免响应过大
        limit = min(total_rows, 500)
        rows = []
        for i in range(limit):
            row = []
            for col in columns:
                val = table.column(col)[i].as_py()
                row.append(val)
            rows.append(row)

        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "total_rows": total_rows,
            "returned_rows": limit,
        }
    except Exception as exc:
        tb = traceback.format_exc()
        logger.exception("Parquet 解析失败")
        return {"ok": False, "msg": str(exc), "traceback": tb}
