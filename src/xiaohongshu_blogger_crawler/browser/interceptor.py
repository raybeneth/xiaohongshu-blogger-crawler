"""
browser.interceptor
-------------------
自动模拟邮箱登录小红书灵感平台，登录成功后加载目标页面并拦截所有接口响应。
支持两种登录方式：
  - 自动登录（LINKX_AUTO_LOGIN=true）：模拟邮箱登录
  - Cookie 登录（LINKX_AUTO_LOGIN=false）：直接注入 XHS_COOKIE
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

from playwright.async_api import BrowserContext, Page, Response, async_playwright

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

# ── 卡片与筛选项配置 ─────────────────────────────────────────────────────────

# 父卡片固定顺序（页面文字）
PARENT_CARD_NAMES: tuple[str, ...] = ("有曝光笔记数", "阅读量", "互动量")

# 子卡片固定顺序（页面文字）
CHILD_CARD_NAMES: tuple[str, ...] = ("整体", "人群", "场景", "买点", "品类产品")

# 每个父卡片对应的第一组筛选项（默认选中项在前）
PARENT_FILTER_MAP: dict[str, tuple[str, str]] = {
    "有曝光笔记数": ("有曝光笔记", "优质笔记数"),
    "阅读量":      ("阅读量",    "深度阅读量"),
    "互动量":      ("互动量",    "深度互动量"),
}

# 「买点」子卡片内的标签列表（第一个为默认选中，依次切换）
MAIDAN_TAG_NAMES: tuple[str, ...] = (
    "不限", "妆容风格", "使用体验", "肤质", "功效",
    "颜色", "外观", "气味", "成分", "包装",
)
# 每个买点标签切换后等待抓取的秒数
MAIDAN_TAG_WAIT_SECONDS: int = 20


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


# ── Cookie 注入 ──────────────────────────────────────────────────────────────

def _parse_cookie_string(raw: str) -> list[dict]:
    """将 'key=value; key2=value2' 格式的 Cookie 字符串解析为 Playwright 所需的列表。"""
    cookies: list[dict] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, _, value = part.partition("=")
        else:
            name, value = part, ""
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": "idea.xiaohongshu.com",
            "path": "/",
        })
    return cookies


async def _inject_cookies(context: BrowserContext, cookie_str: str) -> None:
    """将 Cookie 字符串注入到浏览器上下文。"""
    cookies = _parse_cookie_string(cookie_str)
    if not cookies:
        logger.warning("Cookie 字符串为空，跳过注入")
        return
    await context.add_cookies(cookies)
    logger.info("已注入 %d 个 Cookie（Cookie 登录模式）", len(cookies))


# ── 主入口 ───────────────────────────────────────────────────────────────────

async def run(
        email: str = LOGIN_EMAIL,
        password: str = LOGIN_PASSWORD,
        target_url: str = TARGET_URL,
        headless: bool = False,
        wait_until: str = "load",
        timeout: int = 60_000,
        auto_login: bool | None = None,
) -> None:
    """
    启动浏览器 → 登录（自动登录或 Cookie 注入）→ 跳转目标页面 → 拦截并记录所有接口响应。

    Parameters
    ----------
    email:      登录邮箱（auto_login=True 时使用）
    password:   登录密码（auto_login=True 时使用）
    target_url: 登录成功后要加载的目标页面
    headless:   是否无头模式（默认 False，方便调试）
    wait_until: 目标页面加载等待事件
    timeout:    目标页面加载超时（毫秒）
    auto_login: 是否自动模拟登录；None 时读取 settings.link_x_auto_login
    """
    if auto_login is None:
        auto_login = settings.link_x_auto_login

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

        if auto_login:
            # 自动模拟登录（登录过程不拦截接口，避免噪音）
            logger.info("自动登录模式：开始模拟邮箱登录")
            print("[登录模式] 自动模拟登录")
            await _login(page, email, password)
        else:
            # Cookie 登录：注入 Cookie 后直接跳转目标页
            logger.info("Cookie 登录模式：注入 Cookie 并直接跳转目标页")
            print("[登录模式] Cookie 登录")
            await _inject_cookies(context, settings.link_x_cookie)

        # 登录成功后再注册响应监听器
        page.on("response", _on_response)

        # 跳转目标页面
        logger.info("正在加载目标页面: %s", target_url)
        await page.goto(target_url, wait_until=wait_until, timeout=timeout)
        logger.info("目标页面加载完毕，开始依次点击统计卡片")

        # 等待统计卡片列表出现
        # 页面上有两组 statistic-card-list：第一组是父卡片，第二组是子卡片
        await asyncio.sleep(10)
        card_lists = page.locator(".statistic-card-list")
        await card_lists.first.wait_for(state="visible", timeout=30_000)

        total_lists = await card_lists.count()
        if total_lists < 2:
            logger.warning("未找到两组卡片列表，仅找到 %d 组，终止抓取", total_lists)
            return

        parent_list = card_lists.nth(0)
        child_list  = card_lists.nth(1)

        # 打印本次将处理的父/子卡片清单
        print(f"[父卡片] 共 {len(PARENT_CARD_NAMES)} 个：{list(PARENT_CARD_NAMES)}")
        print(f"[子卡片] 共 {len(CHILD_CARD_NAMES)} 个：{list(CHILD_CARD_NAMES)}")
        logger.info("父卡片：%s", PARENT_CARD_NAMES)
        logger.info("子卡片：%s", CHILD_CARD_NAMES)

        parent_count = len(PARENT_CARD_NAMES)
        child_count  = len(CHILD_CARD_NAMES)

        for pi, parent_name in enumerate(PARENT_CARD_NAMES):
            filter_labels = PARENT_FILTER_MAP[parent_name]   # 固定两个筛选项
            filter_count  = len(filter_labels)

            print(
                f"\n[父卡片 {pi + 1}/{parent_count}]「{parent_name}」"
                f" | 筛选项({filter_count})：{list(filter_labels)}"
                f" | 子卡片({child_count})：{list(CHILD_CARD_NAMES)}"
            )
            logger.info(
                "[父 %d/%d]「%s」筛选项：%s，子卡片：%s",
                pi + 1, parent_count, parent_name, filter_labels, CHILD_CARD_NAMES,
            )

            # 在父卡片列表中按文字定位并点击
            parent_card = parent_list.locator(
                f".statistic-card-wrapper:has(.statistic-card-title:has-text('{parent_name}'))"
            )
            await parent_card.scroll_into_view_if_needed()
            await parent_card.click()

            # 等待页面稳定后开始筛选项循环
            await asyncio.sleep(10)

            # 第一组 segment-control 容器（页面可能有多组，只处理第一组）
            first_segment = page.locator('[style*="segment-control-padding"]').first

            for fi, filter_label in enumerate(filter_labels):
                if fi == 0:
                    # 第一个筛选项默认已选中，无需点击
                    print(
                        f"  [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
                        f"「{filter_label}」默认选中，开始抓取子卡片..."
                    )
                    logger.info(
                        "  [父 %d/%d][筛选 %d/%d]「%s」默认选中，开始抓取子卡片...",
                        pi + 1, parent_count, fi + 1, filter_count, filter_label,
                    )
                else:
                    # 在第一组 segment-control 内按文字点击目标筛选项
                    filter_item = first_segment.locator(f'.d-segment-item:has-text("{filter_label}")')
                    await filter_item.click()
                    print(
                        f"  [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
                        f"「{filter_label}」已切换，等待20s 数据刷新..."
                    )
                    logger.info(
                        "  [父 %d/%d][筛选 %d/%d]「%s」已切换，等待20s 数据刷新...",
                        pi + 1, parent_count, fi + 1, filter_count, filter_label,
                    )
                    await asyncio.sleep(20)

                for ci, child_name in enumerate(CHILD_CARD_NAMES):
                    # 灵犀页面渲染较慢，先等待再操作
                    await asyncio.sleep(20)

                    # 在子卡片列表中按文字定位
                    child_card = child_list.locator(
                        f".statistic-card-wrapper:has(.statistic-card-title:has-text('{child_name}'))"
                    )
                    await child_card.click()

                    if child_name == "买点":
                        await reasons_for_purchase_crawler(pi, ci, fi, filter_count, parent_count, child_count,
                                                           child_name, page)
                    else:
                        print(
                            f"    [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
                            f"[子 {ci + 1}/{child_count}]「{child_name}」已点击，等待10s 抓取数据..."
                        )
                        logger.info(
                            "  [父 %d/%d][筛选 %d/%d][子 %d/%d]「%s」已点击，等待10s 抓取数据...",
                            pi + 1, parent_count, fi + 1, filter_count, ci + 1, child_count, child_name,
                        )
                        await asyncio.sleep(10)

                print(
                    f"  [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
                    f"「{filter_label}」所有子卡片抓取完毕"
                )
                logger.info(
                    "  [父 %d/%d][筛选 %d/%d]「%s」所有子卡片抓取完毕",
                    pi + 1, parent_count, fi + 1, filter_count, filter_label,
                )

            print(f"[父卡片 {pi + 1}/{parent_count}]「{parent_name}」所有筛选条件抓取完毕")
            logger.info("[父 %d/%d]「%s」所有筛选条件抓取完毕", pi + 1, parent_count, parent_name)

        print("\n所有父/子卡片点击完毕，数据抓取结束。")
        logger.info("所有父/子卡片点击完毕，数据抓取结束。")
        # await browser.close()


async def reasons_for_purchase_crawler(pi, ci, fi, filter_count, parent_count, child_count, child_name, page) -> None:
    # 「买点」需要依次切换内部标签（共 10 个），每个等待 15s 抓取数据
    tag_count = len(MAIDAN_TAG_NAMES)
    print(
        f"    [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
        f"[子 {ci + 1}/{child_count}]「{child_name}」已点击，"
        f"开始遍历 {tag_count} 个买点标签..."
    )
    logger.info(
        "  [父 %d/%d][筛选 %d/%d][子 %d/%d]「买点」已点击，开始遍历 %d 个标签",
        pi + 1, parent_count, fi + 1, filter_count, ci + 1, child_count, tag_count,
    )
    # 等待买点标签区域渲染
    await asyncio.sleep(10)
    for ti, tag_name in enumerate(MAIDAN_TAG_NAMES):
        if ti > 0:
            # 按文字定位并点击标签（第一个"不限"默认已选中）
            # 标签渲染为 <button class="d-button ...">，文字前后带有空白
            tag_item = page.locator(f'button.d-button:has-text("{tag_name}")').first
            await tag_item.click()
        print(
            f"      [买点标签 {ti + 1}/{tag_count}]「{tag_name}」"
            f"{'默认选中' if ti == 0 else '已切换'}，"
            f"等待{MAIDAN_TAG_WAIT_SECONDS}s 抓取数据..."
        )
        logger.info(
            "  [买点标签 %d/%d]「%s」%s，等待%ds",
            ti + 1, tag_count, tag_name,
            "默认选中" if ti == 0 else "已切换",
            MAIDAN_TAG_WAIT_SECONDS,
        )
        await asyncio.sleep(MAIDAN_TAG_WAIT_SECONDS)
    print(
        f"    [父 {pi + 1}/{parent_count}][筛选 {fi + 1}/{filter_count}]"
        f"[子 {ci + 1}/{child_count}]「{child_name}」所有买点标签抓取完毕"
    )
    logger.info(
        "  [父 %d/%d][筛选 %d/%d][子 %d/%d]「买点」所有标签抓取完毕",
        pi + 1, parent_count, fi + 1, filter_count, ci + 1, child_count,
    )

# ── 直接运行 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pathlib

    log_path = pathlib.Path("logs/browser_interceptor.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _handler = logging.FileHandler(log_path, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logging.basicConfig(level=logging.INFO, handlers=[_handler])

    print(f"日志输出至: {log_path.resolve()}")
    asyncio.run(run(headless=False))
