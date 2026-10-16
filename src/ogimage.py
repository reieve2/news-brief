"""抓文章页的 og:image（社交卡片图），给视频卡片当素材。

只取一手来源页面上的官方配图，不去抓媒体的加工图——版权上更干净，观感上也更像「证据」。
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import urljoin, urlparse

from common import resolve_local_path

logger = logging.getLogger("brief")

# og:image 的三种常见写法
META_PATTERNS = [
    re.compile(
        r'<meta[^>]+(?:property|name)=["\']og:image(?::url)?["\'][^>]*?content=["\']([^"\']+)["\']',
        re.I,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\']og:image(?::url)?["\']',
        re.I,
    ),
]

IMAGE_EXT = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)

# 只从这些站点抓题图。媒体站的 og:image 经常是文章配图——人物照、场景照都有，
# 版权和肖像权都比官方素材含糊；官方博客的图基本是自己做的宣传图，干净得多。
OFFICIAL_HOSTS = (
    "openai.com",
    "deepmind.google",
    "blog.google",
    "research.google",
    "machinelearning.apple.com",
    "aws.amazon.com",
    "pytorch.org",
    "bair.berkeley.edu",
    "blogs.nvidia.com",
    "microsoft.com",
    "huggingface.co",
    "arxiv.org",
    "github.blog",
    "ai.meta.com",
)


def is_official(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def normalize(candidate: str, base_url: str) -> str:
    url = html.unescape(candidate.strip())
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(base_url, url)
    return url


def extract(html_text: str, base_url: str) -> str:
    for pattern in META_PATTERNS:
        match = pattern.search(html_text)
        if match:
            url = normalize(match.group(1), base_url)
            if url.startswith("http"):
                return url
    # 退一步：twitter:image 也常常是同一张
    match = re.search(
        r'<meta[^>]+(?:property|name)=["\']twitter:image["\'][^>]*?content=["\']([^"\']+)["\']',
        html_text,
        re.I,
    )
    if match:
        url = normalize(match.group(1), base_url)
        if url.startswith("http"):
            return url
    return ""


def fetch_image_url(cfg: dict, session, url: str, use_proxy: bool = True) -> str:
    """打开文章页，找它的题图地址。失败返回空串。"""
    from fetch import get

    response = get(session, cfg, url, use_proxy=use_proxy, timeout=20)
    if response is None:
        logger.debug("抓页面失败：%s", url)
        return ""
    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type and "xml" not in content_type:
        logger.debug("不是网页，跳过：%s（%s）", url, content_type)
        return ""
    image = extract(response.text, url)
    if image:
        host = urlparse(image).netloc
        logger.debug("题图 %s -> %s", urlparse(url).netloc, host)
    return image


def download_image(cfg: dict, session, image_url: str, target, use_proxy: bool = True) -> bool:
    """把题图下载到 target（Path）。"""
    from fetch import get

    response = get(session, cfg, image_url, use_proxy=use_proxy, timeout=30)
    if response is None:
        return False
    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type:
        logger.debug("不是图片：%s（%s）", image_url, content_type)
        return False
    if len(response.content) < 1024:
        logger.debug("图片太小，可能是占位图：%s", image_url)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return True


def proxy_map(cfg: dict) -> dict[str, bool]:
    """源名字 → 要不要走代理，用来决定图片请求怎么发。"""
    return {s.get("name", ""): bool(s.get("proxy", True)) for s in cfg.get("sources", [])}


def find_for_sources(
    cfg: dict, session, sources: list[dict], proxies: dict[str, bool]
) -> tuple[str, str, bool]:
    """挨个试这条新闻的来源页，返回第一个抓到题的 (图片URL, 来源URL)。

    中文媒体常常没有 og:image，但同一件事往往还挂着官方来源，
    所以顺序试比只试第一条更可能拿到图，而且官方图版权上更干净。
    """
    for source in sources:
        url = (source.get("url") or "").strip()
        if not url.startswith("http"):
            continue
        if not is_official(url):
            logger.debug("跳过非官方来源：%s", url[:70])
            continue
        use_proxy = proxies.get(source.get("name", ""), True)
        image = fetch_image_url(cfg, session, url, use_proxy=use_proxy)
        if image:
            return image, url, use_proxy
    return "", "", True
