# browser 模块

使用 Playwright 驱动 Chromium，加载需登录的小红书灵感页面，拦截并记录所有 XHR/Fetch 接口响应。

## 依赖安装

```bash
pip install playwright
playwright install chromium
```

## 配置

在 `interceptor.py` 顶部填写两个字段：

| 变量 | 说明 |
|---|---|
| `COOKIE_PLACEHOLDER` | 从浏览器 DevTools → Network 任意请求头中复制完整 Cookie 字符串 |
| `X_S_COMMON` | 同一请求头中的 `x-s-common` 字段值 |

Cookie 格式：`key1=value1; key2=value2; ...`，直接粘贴即可，代码会自动解析。

> Cookie 和 x-s-common 均有时效性，失效后需重新从浏览器抓取。

## 运行

```bash
python -m xiaohongshu_blogger_crawler.browser.interceptor
```

启动后会弹出 Chromium 窗口，页面加载完成后等待 120 秒再关闭（便于调试）。
所有接口响应写入 `logs/browser_interceptor.log`，控制台只打印日志文件路径。

## 日志格式

```
2026-04-13 10:23:01,234 INFO [RESPONSE] 200 GET https://idea.xiaohongshu.com/api/...
{"code":0,"data":{...}}
--------------------------------------------------------------------------------
```

只记录以下资源类型，CSS/JS/图片/字体等静态资源自动过滤：

- `document` — 主页面
- `xhr` / `fetch` — 接口请求
- `websocket` / `eventsource` — 长连接

## 代码调用

```python
from xiaohongshu_blogger_crawler.browser import run
import asyncio

asyncio.run(run(headless=False))  # headless=True 为无头模式
```
