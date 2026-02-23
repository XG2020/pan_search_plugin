"""网盘搜索插件

根据关键词在主流网盘（百度、阿里、夸克、123等）中搜索公开分享资源，返回资源名称与直链。
"""

from __future__ import annotations

import httpx
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger
from pydantic import Field

# ---------- 插件元数据 ----------
plugin = NekroPlugin(
    name="网盘搜索插件",
    module_name="pan_search",
    description="根据关键词搜索网盘资源并返回名称与链接",
    version="1.0.1",
    author="XGGM",
    url="https://github.com/XG2020/pan_search_plugin",
)

# ---------- 配置 ----------
@plugin.mount_config()
class PanSearchConfig(ConfigBase):
    """网盘搜索配置"""

    API_URL: str = Field(
        default="https://so.slowread.net/search",
        title="搜索接口地址",
        description="慢读网盘搜索 POST 地址",
    )
    TIMEOUT: int = Field(
        default=20,
        title="请求超时(秒)",
        description="单次的 HTTP 超时时间",
    )
    USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        title="浏览器 UA",
        description="伪装浏览器 User-Agent",
    )


# ---------- HTML 解析器 ----------
class ResultExtractor(HTMLParser):
    """从搜索结果页提取网盘名称、标题与链接"""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[tuple[str, str, str]] = []
        self._in_card = False
        self._card_depth = 0
        self._pan_name: str = ""
        self._href: str | None = None
        self._text_parts: list[str] = []
        self._title: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "div":
            class_value = attrs_dict.get("class") or ""
            if "result-card" in class_value:
                self._in_card = True
                self._card_depth = 1
                self._pan_name = ""
                self._href = None
                self._text_parts = []
                self._title = ""
                self._in_title = False
            return
        if not self._in_card:
            return
        if tag == "div":
            self._card_depth += 1
            return
        if tag == "img":
            self._pan_name = (attrs_dict.get("alt") or "").strip()
            return
        if tag == "a":
            href = attrs_dict.get("href") or attrs_dict.get("data-url") or attrs_dict.get("data-href")
            if href:
                self._href = href.strip().strip("`")
            return
        if tag == "h3":
            self._in_title = True
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_card and self._in_title:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_card:
            return
        if tag == "h3":
            text = "".join(self._text_parts).strip()
            if text:
                self._title = text.strip("`").strip()
            self._text_parts = []
            self._in_title = False
            return
        if tag == "div":
            self._card_depth -= 1
            if self._card_depth > 0:
                return
            if self._href and self._title:
                pan_name = self._pan_name or "未知网盘"
                self.results.append((pan_name, self._title, self._href))
            self._in_card = False
            self._card_depth = 0
            self._pan_name = ""
            self._href = None
            self._title = ""
            self._text_parts = []
            self._in_title = False


# ---------- 工具函数 ----------
def _is_result_link(url: str) -> bool:
    """判断 URL 是否为真实网盘分享链接"""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    if host == "so.slowread.net":
        return False
    keywords = (
        "quark", "aliyun", "alipan", "baidu", "pan", "xunlei",
        "189.cn", "tianyi", "115", "123pan", "pikpak", "terabox",
        "lanzou", "onedrive", "sharepoint", "drive.google", "google", "uc",
    )
    return any(k in host for k in keywords)


# ---------- 插件方法 ----------
@plugin.mount_sandbox_method(
    SandboxMethodType.BEHAVIOR,
    name="搜索网盘资源",
    description="根据关键词搜索网盘资源并返回名称与链接，最多返回 20 条结果",
)
async def search_pan_resources(_ctx: AgentCtx, query: str) -> str:
    """搜索公开分享的网盘资源,返回资源名称与直链。

    Args:
        query: 搜索关键词，例如 "流浪地球 4K"

    Returns:
        发送格式化的结果字符串消息；若未命中则返回友好提示

    Example:
        result = search_pan_resources("流浪地球 4K")
        send_msg_text(_ck, result)
    """
    config = plugin.get_config(PanSearchConfig)
    keyword = query.strip()
    if not keyword:
        return "请输入搜索关键词。"

    payload = {"pan_type": "", "query": keyword}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://so.slowread.net",
        "Referer": "https://so.slowread.net/",
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
            response = await client.post(config.API_URL, data=payload, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"网盘搜索 HTTP 错误  keyword={keyword}  status={e.response.status_code}")
        return "搜索服务返回异常，请稍后重试。"
    except httpx.RequestError as e:
        logger.error(f"网盘搜索网络错误  keyword={keyword}  error={e}")
        return "无法连接到搜索服务，请稍后重试。"
    except Exception as e:
        logger.error(f"网盘搜索未知错误  keyword={keyword}  error={e}")
        return "搜索过程发生未知错误，请稍后重试。"

    extractor = ResultExtractor()
    extractor.feed(response.text)

    seen: set[tuple[str, str, str]] = set()
    results: list[tuple[str, str, str]] = []
    for pan_name, title, href in extractor.results:
        if not title or not href:
            continue
        full_url = urljoin(config.API_URL, href)
        if not _is_result_link(full_url):
            continue
        key = (pan_name, title, full_url)
        if key in seen:
            continue
        seen.add(key)
        results.append((pan_name, title, full_url))

    if not results:
        return f"未找到与“{keyword}”相关的资源。"

    lines = [f"搜索关键词：{keyword}"]
    for idx, (pan_name, title, url) in enumerate(results[:20], 1):
        lines.append(f"{idx}. 【{pan_name}】{title} - {url}")
    return "\n".join(lines)


# ---------- 清理 ----------
@plugin.mount_cleanup_method()
async def clean_up() -> None:
    """插件卸载时清理资源（当前无持久化资源，仅打印日志）"""
    logger.info("网盘搜索插件资源已清理")
