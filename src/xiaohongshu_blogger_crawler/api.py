from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from xiaohongshu_blogger_crawler.config import settings
from xiaohongshu_blogger_crawler.services.crawler_service import CrawlerService

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
        const resp = await fetch('/api/search?nickname=' + encodeURIComponent(nickname));
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


@app.get("/api/search")
async def search_blogger(
    nickname: str = Query(..., min_length=1, description="达人昵称"),
) -> JSONResponse:
    service = CrawlerService(settings)
    result = await service.search_by_name(nickname)
    data = result.model_dump(mode="json")
    data["is_found"] = result.is_found
    return JSONResponse(content=data)
