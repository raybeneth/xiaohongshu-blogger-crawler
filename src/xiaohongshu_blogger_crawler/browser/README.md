# browser 模块

使用 Playwright 驱动 Chromium，自动完成邮箱登录后加载目标页面，拦截并记录所有 XHR/Fetch 接口响应。

## 依赖安装

```bash
pip install playwright
playwright install chromium
```

## 配置

在 `interceptor.py` 顶部填写账号信息：

| 变量 | 说明 |
|---|---|
| `LOGIN_EMAIL` | 登录邮箱 |
| `LOGIN_PASSWORD` | 登录密码 |
| `TARGET_URL` | 登录成功后跳转的目标页面 |

## 运行

```bash
python -m xiaohongshu_blogger_crawler.browser.interceptor
```

运行流程：
1. 弹出 Chromium 窗口，加载登录页
2. 自动点击「邮箱登录」切换入口
3. 填写邮箱和密码并提交
4. 登录成功后自动跳转到 `TARGET_URL`
5. 等待 120 秒（便于调试），期间所有接口响应写入日志

日志文件路径：`logs/browser_interceptor.log`

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

asyncio.run(run(
    email="your@email.com",
    password="your_password",
    headless=False,   # True 为无头模式
))
```

## 页面元素说明

登录流程依赖以下页面元素，若小红书改版导致登录失败，需同步调整 `interceptor.py` 中 `_login()` 函数的选择器：

| 操作 | 当前选择器 |
|---|---|
| 切换邮箱登录 | `get_by_text("邮箱登录", exact=True)` |
| 邮箱输入框 | `get_by_placeholder("请输入邮箱")` |
| 密码输入框 | `get_by_placeholder("请输入密码")` |
| 登录按钮 | `get_by_role("button", name="登录")` |
