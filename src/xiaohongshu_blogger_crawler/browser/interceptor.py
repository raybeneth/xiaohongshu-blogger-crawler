"""
browser.interceptor
-------------------
打开无头浏览器，加载指定页面，拦截并打印所有接口返回内容。

使用前请将 COOKIE_PLACEHOLDER 替换为真实 Cookie 字符串，
或在调用 run() 时通过参数传入。
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets

from playwright.async_api import Page, Response, async_playwright

logger = logging.getLogger(__name__)

# ── 配置区 ──────────────────────────────────────────────────────────────────

TARGET_URL = (
    "https://idea.xiaohongshu.com/idea/creativity/ContentInsight"
    "?id=213943758&startTime=2026-01-01&endTime=2026-03-31"
)

# 请将此处替换为真实 Cookie 字符串（key=value; key2=value2 格式）
COOKIE_PLACEHOLDER = "abRequestId=9c4d84d4-4f39-5dd2-9bea-022d2f0083cb; a1=19abe436ef1ph0uirr4d8s6ttw4euce4sauytpu7o50000194913; webId=d44505455a44b0d71b1aacf90b50839d; gid=yjD8WJYK0jM8yj0Dd4qKd0U7iyUx873FF4fY7WlMK99E4v28d7Sd49888yj4jyq8SJSy8yJ2; ets=1775112281055; web_session=040069b8ba071d9f986b2bf6e13b4b7501f009; id_token=VjEAABg8PqSbzjlSybFMoW87j8FzSZ/pOyq/WbYNKRZfwvBlgtcQSq6qe2rVCypv0nV4NmWJILr3qIxiqIrUpMXCkjYoLUIo5D+tF5fH5Xc1jnYNBVTI41c+rCjAko1ne+rIqkNQ; xsecappid=ads-idea; customer-sso-sid=68c517628156458128310274kxzls6aeqms1j1wa; x-user-id-idea.xiaohongshu.com=69c36f372788000000000000; customerClientId=428706455041674; idea.outer.sso.token=AT-68c517628156458128146434dn7ntskrcniiwupc; access-token-idea.xiaohongshu.com=customer.idea.AT-68c517628156458128146434dn7ntskrcniiwupc; idea.outer.loginType.path=AT-68c517628156458128146434dn7ntskrcniiwupc; websectiga=10f9a40ba454a07755a08f27ef8194c53637eba4551cf9751c009d9afb564467; sec_poison_id=e4a27e6b-c1fa-40af-9bf8-075ceec9868e; acw_tc=0a0d037c17760736086428937e2147fed0d9bb9f471437e155b25b4dd35d40; loadts=1776073609104"
# X_S_COMMON = "2UQAPsHC+aIjqArjwjHjNsQhPsHCH0rjNsQhPaHCH0c1PahFHjIj2eHjwjQgynEDJ74AHjIj2ePjwjQY8oPTynzSGaHVHdWFH0ijPahlN0HMHjIj2eLjwjHlwnbj8/cA+fpfPgmiPopkqdHF8eYA+dzF4AzS4n+S+o+Y4gSFqoL7JALIPeZIP/DFw/rAHjIj2eGjwjHjNsQh+UHCHjHVHdWhH0ija/PhqDYD87+xJ7mdag8Sq9zn494QcUT6aLpPJLQy+nLApd4G/B4BprShLA+jqg4bqD8S8gYDPBp3Jf+m2DMBnnEl4BYQyrkSzBE+zrTM4bQQPFTAnnRUpFYc4r4UGSGILeSg8DSkN9pgGA8SngbF2pbmqbmQPA4Sy9Ma+SbPtApQy/8A8BES8p+fqpSHqg4VPdbF+LHIzrQQ2sTczFzkN7+n4BTQ2BzA2op7q0zl4BSQyopYaLLA8/+Pp0mQPM8LaLP78/mM4BIUcLzTqFl98Lz/a7+/LoqMaLp9q9Sn4rkOqgqhcdp78SmI8BpLzS4OagWFprSk4/8yLo4ULopF+LS9JBbPGf4AP7bF2rSh8gPlpd4HanTMJLS3agSSyf4AnaRgpB4S+9p/qgzSNFc7qFz0qBSI8nzSngQr4rSe+fprpdqUaLpwqM+l4Bl1Jb+M/fkn4rS9J9p3qgcAGMi7qM86+B4Qzp+EanYbwsVEzbpQ4dkE+rDh/FSkGA4yLo4mag8kw/z6N7+r/BzA+Sm7pDSe+9p/8e4A+0SQJLSi+dPA2dQDLgpF+LSbJ7PAy0pS2rltqM8c49+Uwn4ALMmF2rSe/pmP89RS8dp7+gk1+g+gpd4Ua/+/2DDA2Sz6Lo4zGp87a9Rpzf4EzDRAzemO8gYM4BMQyFkSnnr6q7W6LLQQ4DRS+fLM8p4VLdQQ4DEAzob7arS3aBS7Lo4P/S8F+DDA/9pk4gzDaLpmq9Sl49lQysRSzobFcLEM4MmTpd4ragYT2rS9Lgmc8rSaaDl98/+l4BYQzLzYanVI8pSM4MbyGDplJ0ZIq9kSab+QzpSNLb87Lg+M4BbQyFkSpSm7zrTg87+3naRS+fQb2LSbafp38sRAy7bFq9Ec47bQcFkSLMm7yLSi+npncLSPagGM8pS6N9LILoz/aL+NqA8c4MGFJ9MlanYH8LSe89pn/BRSpB498pSj+fLlqg4yanY3yDS9a/pYqg48a/+cyDS3/fLlyflL2LHA8nTc49pQyLYYG7b7nrYDN9pgpApApMmFGAzM4rQQyM8xaLL3JfQn4BF3Lo47a/PIq9zCafpgqg4haM8FaLSe+b+wqgzTanTUyFYVyB8Q2BzAzrG9qAmD4fLALo4MaopF2LDAzfRQ2BRAPM8FnLSi4fLIzbcEaL+b8g+ypB4Q40Y7aLP78gYM4ApdpdzFLb8FpLShqpYQyrEAprrI8nSl4FEdL7Q+aL+i4rTn4o+j4gzaagYcnLDALn+QyM+VanWI8p8PP7+n/nlp/M872LS9GFpP4g4IGS87cLSb4fLl8SkQanSBygmD+9p/pdzVqS8FaFYTyrES8M8ranSza9bn4MkQyA4AyLSCGFShzaRjLo4ManTC8pkM4b4ALoz0anYgJLS9GD+QcAW3J7p7wLShLomQznpAygp7yfR0JebQyBSPaL+DqMSs/7+3Lo40ag8zJrSbzBYInpmBaL+CL94VaemQ4DbAnn498nkM47bQznRAPMmFaDSinDEQz/mAL7b7GFS9nnpApd4maLP9qM8CyrR04gzmqgbFtUHVHdWEH0iT+eHAw/GUPerVHdWlPsHCPsIj2erlH0ijJBSF8aQR"

# 只记录这些资源类型（排除 css/js/图片/字体等静态资源）
_LOG_RESOURCE_TYPES = {"document", "xhr", "fetch", "websocket", "eventsource"}


# ── 响应回调（Python 层拦截）────────────────────────────────────────────────

async def _on_response(response: Response) -> None:
    resource_type = response.request.resource_type
    if resource_type not in _LOG_RESOURCE_TYPES:
        return

    url = response.url
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
    url: str = TARGET_URL,
    cookie: str = COOKIE_PLACEHOLDER,
    headless: bool = True,
    wait_until: str = "networkidle",
    timeout: int = 60_000,
) -> None:
    """
    启动无头浏览器，加载 *url*，拦截所有接口响应并打印到控制台。

    Parameters
    ----------
    url:        目标页面地址
    cookie:     Cookie 字符串（key=value; key2=value2 格式）
    headless:   是否无头模式
    wait_until: 等待页面加载的事件（networkidle / load / domcontentloaded）
    timeout:    页面加载超时（毫秒）
    """

    if not cookie:
        logger.warning("Cookie 为空，页面可能因未登录而无法加载数据。")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                # "x-s-common": X_S_COMMON,
                "referer": url,
                "x-b3-traceid": secrets.token_hex(8),
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            ignore_https_errors=True,
        )

        # 将 Cookie 写入浏览器 Cookie 存储
        # domain 用 .xiaohongshu.com（带点前缀），使所有子域（SSO、idea 等）均可携带，
        # 避免跨子域重定向时因找不到 Cookie 而被 SSO 重新写入新 session 覆盖原值
        parsed_cookies = [
            {"name": k.strip(), "value": v.strip(), "domain": ".xiaohongshu.com", "path": "/"}
            for part in cookie.split(";")
            if "=" in part
            for k, _, v in [part.strip().partition("=")]
        ]
        await context.add_cookies(parsed_cookies)

        page: Page = await context.new_page()

        # Python 层拦截所有网络响应（含 xhr/fetch/document，过滤静态资源）
        page.on("response", _on_response)

        logger.info("正在加载页面: %s", url)

        await page.goto(url, wait_until=wait_until, timeout=timeout)

        logger.info("页面加载完毕，所有接口响应已写入日志。")
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
    asyncio.run(run(headless=False))
