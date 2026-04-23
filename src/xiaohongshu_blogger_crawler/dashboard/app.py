from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from xiaohongshu_blogger_crawler.dashboard.database import close_pool, init_pool
from xiaohongshu_blogger_crawler.dashboard.task_manager import list_subscriptions

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
