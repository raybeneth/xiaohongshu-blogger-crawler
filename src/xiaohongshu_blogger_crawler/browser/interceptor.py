"""
browser.interceptor
-------------------
自动模拟邮箱登录小红书灵感平台，登录成功后加载目标页面并拦截所有接口响应。
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from playwright.async_api import Page, Response, async_playwright

from xiaohongshu_blogger_crawler.config import settings

logger = logging.getLogger(__name__)

# ── 配置区 ──────────────────────────────────────────────────────────────────

LOGIN_URL = "https://idea.xiaohongshu.com/login"

TARGET_URL = (
    "https://idea.xiaohongshu.com/idea/creativity/ContentInsight"
    "?id=213943758&startTime=2026-01-01&endTime=2026-03-31"
)

# 登录账号（替换为真实值）
LOGIN_EMAIL = settings.link_x_account
LOGIN_PASSWORD = settings.link_x_password

# 只记录这些资源类型（排除 css/js/图片/字体等静态资源）
_LOG_RESOURCE_TYPES = {"document", "xhr", "fetch", "websocket", "eventsource"}


# ── 登录流程 ─────────────────────────────────────────────────────────────────

async def _login(page: Page, email: str, password: str) -> None:
    """
    在登录页完成邮箱登录：
    1. 加载登录页
    2. 点击右上角「邮箱登录」切换入口
    3. 填写邮箱与密码并提交
    4. 等待跳转离开登录页，确认登录成功
    """
    logger.info("加载登录页: %s", LOGIN_URL)
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")

    # 点击邮箱登录图标按钮（通过 SVG path 特征定位信封图标）
    email_icon_btn = page.locator("button:has(svg path[d*='M18.3333 6H5.66667'])")
    await email_icon_btn.wait_for(state="visible", timeout=10_000)
    await email_icon_btn.click()
    logger.info("已切换至邮箱登录")

    # 等待邮箱输入框可见（切换面板有动画，需等渲染完成）
    email_input = page.get_by_placeholder("请输入邮箱")
    await email_input.wait_for(state="visible", timeout=10_000)

    # 填写邮箱和密码
    await email_input.fill(email)
    await page.get_by_placeholder("请输入密码").fill(password)

    # 勾选隐私协议
    # 页面使用 d- 组件库，checkbox 通常是 .d-checkbox 包裹的自定义组件，
    # 优先点击 wrapper，若找不到再降级到原生 input
    privacy = page.locator(".d-checkbox").first
    if await privacy.count() > 0:
        if not await privacy.locator("input[type='checkbox']").is_checked():
            await privacy.click()
    else:
        raw = page.locator("input[type='checkbox']").first
        if not await raw.is_checked():
            await raw.click()
    logger.info("已勾选隐私协议")

    # 点击登录按钮
    await page.get_by_role("button", name="登录").click()
    logger.info("已提交登录表单，等待跳转...")

    # 等待离开登录页（最长 30 秒）
    await page.wait_for_url(
        lambda u: "/login" not in u,
        timeout=30_000,
    )
    logger.info("登录成功，当前页面: %s", page.url)


# ── 响应回调（Python 层拦截）────────────────────────────────────────────────

async def _on_response(response: Response) -> None:
    url = response.url
    if not re.search(r"/api/idea/chartview/[^/?]+$", url.split("?")[0]):
        return
    try:
        body_bytes = await response.body()
        try:
            body = json.loads(body_bytes)
            body_str = json.dumps(body, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_str = body_bytes.decode("utf-8", errors="replace")

        logger.info(
            "[RESPONSE] %s %s %s\n%s\n%s",
            response.status,
            response.request.method,
            url,
            body_str,
            "-" * 80,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取响应体失败 %s: %s", url, exc)


# ── 主入口 ───────────────────────────────────────────────────────────────────

async def run(
        email: str = LOGIN_EMAIL,
        password: str = LOGIN_PASSWORD,
        target_url: str = TARGET_URL,
        headless: bool = False,
        wait_until: str = "networkidle",
        timeout: int = 60_000,
) -> None:
    """
    启动浏览器 → 邮箱登录 → 跳转目标页面 → 拦截并记录所有接口响应。

    Parameters
    ----------
    email:      登录邮箱
    password:   登录密码
    target_url: 登录成功后要加载的目标页面
    headless:   是否无头模式（默认 False，方便调试）
    wait_until: 目标页面加载等待事件
    timeout:    目标页面加载超时（毫秒）
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"accept-language": "zh-CN,zh;q=0.9,en;q=0.8"},
            ignore_https_errors=True,
        )

        page: Page = await context.new_page()

        # 登录（登录过程不拦截接口，避免噪音）
        await _login(page, email, password)

        # 登录成功后再注册响应监听器
        page.on("response", _on_response)

        # 跳转目标页面
        logger.info("正在加载目标页面: %s", target_url)
        await page.goto(target_url, wait_until=wait_until, timeout=timeout)
        logger.info("目标页面加载完毕，开始依次点击统计卡片")

        # 等待统计卡片列表出现
        cards = page.locator(".statistic-card-list .statistic-card-wrapper.could-selected")
        await cards.first.wait_for(state="visible", timeout=30_000)

        total = await cards.count()
        logger.info("共找到 %d 个统计卡片", total)

        for i in range(total):
            card = cards.nth(i)
            title = await card.locator(".statistic-card-title").inner_text()
            await card.click()
            logger.info("[%d/%d] 已点击卡片「%s」，等待 20s 抓取数据...", i + 1, total, title)
            await asyncio.sleep(20)

        logger.info("所有卡片点击完毕，数据抓取结束。")
        await browser.close()


# ── 直接运行 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pathlib

    log_path = pathlib.Path("logs/browser_interceptor.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _handler = logging.FileHandler(log_path, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logging.basicConfig(level=logging.INFO, handlers=[_handler])

    print(f"日志输出至: {log_path.resolve()}")
    asyncio.run(run())
