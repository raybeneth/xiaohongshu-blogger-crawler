from __future__ import annotations

import asyncio
import dataclasses
import logging
import random
from typing import List

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from xiaohongshu_blogger_crawler.config import settings
from xiaohongshu_blogger_crawler.models.search_result import BloggerSearchResult
from xiaohongshu_blogger_crawler.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)

app = FastAPI(title="小红书达人查询", version="0.1.0")

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>小红书达人查询</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f5f5f5;
      display: flex;
      justify-content: center;
      padding: 60px 16px;
      min-height: 100vh;
    }
    .card {
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 12px rgba(0,0,0,.08);
      padding: 36px 40px;
      width: 100%;
      max-width: 1200px;
      height: fit-content;
    }
    h1 {
      font-size: 22px;
      color: #ff2442;
      margin-bottom: 24px;
      text-align: center;
    }
    .search-row {
      display: flex;
      gap: 10px;
    }
    input[type="text"] {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #ddd;
      border-radius: 8px;
      font-size: 15px;
      outline: none;
      transition: border-color .2s;
    }
    input[type="text"]:focus { border-color: #ff2442; }
    button {
      padding: 10px 22px;
      background: #ff2442;
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 15px;
      cursor: pointer;
      white-space: nowrap;
      transition: background .2s;
    }
    button:hover { background: #e01f3a; }
    button:disabled { background: #ccc; cursor: not-allowed; }
    #result {
      margin-top: 24px;
    }
    .status-found {
      display: inline-block;
      padding: 2px 10px;
      background: #e6f7ec;
      color: #27a048;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
    }
    .status-not-found {
      display: inline-block;
      padding: 2px 10px;
      background: #fff0f0;
      color: #cc0000;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 600;
    }
    .info-table { width: 100%; border-collapse: collapse; margin-top: 14px; }
    .info-table td { padding: 8px 4px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
    .info-table td:first-child { color: #888; width: 90px; }
    a { color: #ff2442; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .loading { color: #888; font-size: 14px; text-align: center; padding: 16px 0; }
    .error { color: #cc0000; font-size: 14px; margin-top: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1>&#x1F4D6; 小红书达人查询</h1>
    <div class="search-row">
      <input type="text" id="nickname" placeholder="输入达人昵称" autofocus>
      <button id="btn" onclick="doSearch()">查询</button>
    </div>
    <div id="result"></div>
  </div>

  <script>
    document.getElementById('nickname').addEventListener('keydown', function(e) {
      if (e.key === 'Enter') doSearch();
    });

    async function doSearch() {
      const nickname = document.getElementById('nickname').value.trim();
      if (!nickname) return;

      const btn = document.getElementById('btn');
      const resultEl = document.getElementById('result');
      btn.disabled = true;
      resultEl.innerHTML = '<p class="loading">查询中，请稍候…</p>';

      try {
        const resp = await fetch('/api/web_search?nickname=' + encodeURIComponent(nickname));
        const data = await resp.json();

        if (!resp.ok) {
          resultEl.innerHTML = '<p class="error">错误：' + (data.detail || resp.statusText) + '</p>';
          return;
        }

        if (data.is_found) {
          const avatarHtml = data.avatar_url
            ? `<img src="${esc(data.avatar_url)}" style="width:56px;height:56px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;">` : '';
          const verifiedBadge = data.official_verified
            ? '<span style="display:inline-block;padding:1px 8px;background:#fff0f3;color:#ff2442;border-radius:10px;font-size:12px;margin-left:6px;">官方认证</span>' : '';
          resultEl.innerHTML = `
            <span class="status-found">已找到</span>
            <table class="info-table">
              <tr><td>头像</td><td>${avatarHtml}</td></tr>
              <tr><td>查询名称</td><td>${esc(data.query_name)}</td></tr>
              <tr><td>匹配昵称</td><td>${esc(data.matched_name || '-')}${verifiedBadge}</td></tr>
              <tr><td>小红书号</td><td>${esc(data.red_id || '-')}</td></tr>
              <tr><td>专业类型</td><td>${esc(data.profession || '-')}</td></tr>
              <tr><td>粉丝数</td><td>${data.followers != null ? data.followers.toLocaleString() : '-'}</td></tr>
              <tr><td>笔记数</td><td>${data.notes != null ? data.notes.toLocaleString() : '-'}</td></tr>
              <tr><td>最近更新</td><td>${esc(data.update_time || '-')}</td></tr>
              <tr><td>主页链接</td><td><a href="${esc(data.profile_url)}" target="_blank">${esc(data.profile_url)}</a></td></tr>
              <tr><td>查询时间</td><td>${new Date(data.scraped_at).toLocaleString('zh-CN')}</td></tr>
            </table>`;
        } else {
          resultEl.innerHTML = `
            <span class="status-not-found">未找到</span>
            <p style="margin-top:12px;font-size:14px;color:#666;">未在小红书搜索结果中找到昵称为「${esc(nickname)}」的达人。</p>`;
        }
      } catch (err) {
        resultEl.innerHTML = '<p class="error">请求失败：' + esc(String(err)) + '</p>';
      } finally {
        btn.disabled = false;
      }
    }

    function esc(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse(content=_HTML)


class CrawlerTaskHeaders(BaseModel):
    cookie: str = Field(..., description="Cookie 字符串")
    xs: str = Field(..., description="X-S 签名")
    xt: str = Field(..., description="X-T 时间戳")
    xs_common: str = Field(..., alias="xs-common", description="X-S-Common 公共签名")

    model_config = {"populate_by_name": True}


class CreateCrawlerTaskRequest(BaseModel):
    nick_names: list[str] = Field(..., max_length=5, description="达人昵称集合")
    headers: CrawlerTaskHeaders = Field(..., description="请求头信息（含 Cookie、xs、xt、xs-common）")


class CreateCrawlerTaskResponse(BaseModel):
    query_name: str = Field(description="查询名称")
    status: str = Field(description="查询结果状态为 NO_FOUND / FOUND")
    matched_name: str = Field(description="匹配名称")
    red_id: str = Field(description="红书号")
    blogger_id: str = Field( description="博主ID")
    avatar_url: str = Field(description="博主头像")
    profile_url: str = Field(description="主页地址")
    followers: int = Field(description="粉丝数")
    notes: int = Field(description="笔记数")
    profession: str = Field(description="专业类型")
    official_verified: bool = Field(description="是否官方认证")
    update_event: str = Field(description="更新时间")

def _to_response(result: BloggerSearchResult) -> CreateCrawlerTaskResponse:
    return CreateCrawlerTaskResponse(
        query_name=result.query_name,
        status="FOUND" if result.is_found else "NOT_FOUND",
        matched_name=result.matched_name or "",
        red_id=result.red_id or "",
        blogger_id=result.blogger_id or "",
        avatar_url=result.avatar_url or "",
        profile_url=result.profile_url or "",
        followers=result.followers or 0,
        notes=result.notes or 0,
        profession=result.profession or "",
        official_verified=result.official_verified or False,
        update_event=result.update_time or "",
    )


@app.post("/api/batch_query")
async def batch_query(
    request: CreateCrawlerTaskRequest,
    x_token: str = Header(..., alias="X-Token", description="API 鉴权 Token"),
) -> List[CreateCrawlerTaskResponse]:
    """
    批量实时爬取达人信息
    达人数一次最多支持查询5条，且每条达人之间有查询等待时间（随机2-6s），单次查询最快也要10s才能返回，调用方需要合理设置超时时间
    避免频繁超时
    """
    logger.info("Request token is %s", x_token[:3] + "********" + x_token[-4:])
    if not settings.api_token or x_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Token 无效或未配置")

    req_settings = dataclasses.replace(
        settings,
        cookie=request.headers.cookie,
        xs=request.headers.xs,
        xt=request.headers.xt,
        xs_common=request.headers.xs_common,
    )
    # 这里的dataclass会将settings设置为新的对象返回，不会存在线程安全问题。且Settings本身添加了frozen=True属性，不会被修改
    service = CrawlerService(req_settings)
    results: List[CreateCrawlerTaskResponse] = []

    for index, nick_name in enumerate(request.nick_names):
        result = await service.search_by_name(nick_name)
        results.append(_to_response(result))
        logger.info("[%d/%d] '%s': %s", index + 1, len(request.nick_names), nick_name, result.is_found)

        if index < len(request.nick_names) - 1:
            wait_seconds = random.uniform(2, 6)
            logger.info("批量查询间隔等待 %.1fs", wait_seconds)
            await asyncio.sleep(wait_seconds)

    return results


@app.get("/api/web_search")
async def search_blogger(
        nickname: str = Query(..., min_length=1, description="达人昵称"),
) -> JSONResponse:
    service = CrawlerService(settings)
    result = await service.search_by_name(nickname)
    data = result.model_dump(mode="json")
    data["is_found"] = result.is_found
    return JSONResponse(content=data)
