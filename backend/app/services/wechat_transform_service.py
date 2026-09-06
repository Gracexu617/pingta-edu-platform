"""公众号文章转化服务：采集 → 提炼 → 重写 → 水印 → 输出。

核心原则（来自 V2.0 规范 + 用户要求）：
- 不抄袭：提取核心观点/数据/案例后，以"凭他教育"视角重写
- 图片：去原水印 + 加「凭他教育」斜向水印
- 表格：双层「凭他教育」防盗水印
- 底部固定品牌文案：「凭他教育升学规划整体解决方案」
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.llm_client import call_llm, call_vision_llm
from app.services.knowledge_card import (
    KnowledgeCard, CardStat, CardTable, build_card_from_data,
    C_NAVY, C_GOLD,
)
from app.services.watermark_remover import remove_watermark

logger = logging.getLogger(__name__)

# ── 品牌常量（V2.0 规范） ──────────────────────────────────────────────

BRAND_NAME = "凭他教育"
# 品牌口号（取自「凭他生涯」公众号真实文末文案）
BRAND_SLOGAN = "理性选校 · 科学定位 · 提前规划，让升学不再迷茫！"
# 文末服务推广文案（取自「凭他生涯」真实推文，保持品牌一致）
BRAND_PROMO = (
    "凭他教育提供志愿填报、强基计划、综合评价、港澳高校、春季高考（高职单招）、"
    "国际本科全过程辅导！我们拥有经验丰富的师资团队，为学生提供一站式服务，"
    "助力考生在多元录取中取得最终胜利。有任何升学疑问，欢迎咨询⬇️"
)
WATERMARK_TEXT = BRAND_NAME
WATERMARK_ALPHA = 0.12  # 半透明
WATERMARK_ANGLE = -30   # 斜向角度

# ── 数据结构 ────────────────────────────────────────────────────────────


@dataclass
class WechatArticleRef:
    """搜索到的公众号文章引用（轻量，不含全文）。"""
    title: str
    url: str  # 微信文章链接或中间页
    summary: str = ""
    account_name: str = ""
    published_at: str = ""


@dataclass
class ArticleImage:
    """文章中的图片。"""
    url: str
    alt_text: str = ""
    is_cover: bool = False
    # 处理后的本地路径 / base64
    processed_data: bytes | None = None
    processed_mime: str = ""


@dataclass
class ArticleTable:
    """文章中的表格数据。"""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    html: str = ""  # 原始 HTML 片段


@dataclass
class ExtractedCore:
    """从原文提炼的核心内容（不抄袭）。"""
    main_thesis: str = ""          # 核心论点(1句)
    key_points: list[str] = field(default_factory=list)   # 分论点(3-5条)
    key_data: list[str] = field(default_factory=list)     # 关键数据/数字
    cases: list[str] = field(default_factory=list)        # 案例
    source_account: str = ""
    source_url: str = ""
    original_title: str = ""
    # ── 知识卡片输入（有值时自动生成凭他教育风格数据卡片嵌入文章）───────
    card_title: str = ""           # 卡片主标题（如校名/主题名）
    card_subtitle: str = ""        # 卡片副标题（如年份+事件）
    card_stats: list[dict] = field(default_factory=list)  # [{"label":"...","value":"...","unit":"..."}]
    card_table_title: str = ""     # 表格区域标题
    card_table_headers: list[str] = field(default_factory=list)  # 表头
    card_table_rows: list[list[str]] = field(default_factory=list)  # 表格数据


@dataclass
class TransformedArticle:
    """转化后的凭他教育风格文章。"""
    title: str
    body_html: str               # 富文本正文（含处理后图片）
    body_text: str               # 纯文本版本
    images: list[ArticleImage] = field(default_factory=list)
    tables: list[ArticleTable] = field(default_factory=list)
    source_account: str = ""
    source_title: str = ""
    source_url: str = ""
    transformed_at: datetime = field(default_factory=datetime.now)
    word_count: int = 0


# ── 1. 公众号文章搜索 ────────────────────────────────────────────────────


SKILL_SEARCH_SCRIPT = Path(
    "/Users/xulehan/.workbuddy/skills/wechat-article-search/scripts/search_wechat.js"
)
NODE_BIN = Path("/Users/xulehan/.workbuddy/binaries/node/versions/22.22.2/bin/node")
NODE_MODULES = Path("/Users/xulehan/.workbuddy/binaries/node/workspace/node_modules")


async def _search_via_skill(
    account_name: str,
    limit: int,
    *,
    resolve_url: bool = True,
    timeout: float = 90.0,
) -> list[WechatArticleRef]:
    """调用 wechat-article-search skill 脚本搜索（首选路径）。

    该脚本已处理 cookie 引导、gzip 解压、中间链接还原等反爬细节，
    比自建 httpx 解析稳定得多，因此优先复用、避免重复造轮子。
    """
    if not SKILL_SEARCH_SCRIPT.exists() or not NODE_BIN.exists():
        logger.info("skill 脚本或 node 不可用，跳过 skill 搜索路径")
        return []

    import json as _json
    import os as _os

    args = [str(NODE_BIN), str(SKILL_SEARCH_SCRIPT), account_name, "-n", str(limit)]
    if resolve_url:
        args.append("-r")

    env = dict(_os.environ)
    env["NODE_PATH"] = str(NODE_MODULES)
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(SKILL_SEARCH_SCRIPT.parent.parent),
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("skill 搜索超时(%s)", account_name)
        return []
    except Exception as e:
        logger.warning("skill 搜索启动失败(%s): %s", account_name, e)
        return []

    raw = stdout.decode("utf-8", errors="ignore")
    # 脚本首行是进度提示（"正在搜索: ..."），需截取 JSON 主体
    start = raw.find("{")
    if start < 0:
        logger.warning("skill 搜索无 JSON 输出: %s", stderr.decode()[:200])
        return []

    try:
        payload = _json.loads(raw[start:])
    except Exception as e:
        logger.warning("skill 搜索 JSON 解析失败: %s", e)
        return []

    out: list[WechatArticleRef] = []
    for item in payload.get("articles", []):
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url:
            continue
        out.append(
            WechatArticleRef(
                title=title,
                url=url,
                summary=(item.get("summary") or "").strip(),
                account_name=(item.get("source") or account_name).strip(),
                published_at=(item.get("datetime") or item.get("date_text") or "").strip(),
            )
        )
    return out


async def search_account_articles(
    account_name: str,
    limit: int = 10,
    *,
    timeout: float = 15.0,
) -> list[WechatArticleRef]:
    """按公众号名搜索其近期文章。

    优先复用 wechat-article-search skill（稳定、已处理反爬）；
    失败时回退到内置 httpx + HTMLParser 解析。
    """
    skill_results = await _search_via_skill(account_name, limit)
    if skill_results:
        return skill_results[:limit]

    results: list[WechatArticleRef] = []

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # 微信搜狗搜索（按公众号名）
            search_url = (
                "https://weixin.sogou.com/weixin2type/w2q/"
                f"?s_from=input&query={account_name}&ie=utf8&s_type=2&page=1"
            )
            resp = await client.get(
                search_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )
            html = resp.text

            # 解析搜索结果
            results = _parse_sogou_weixin_results(html, account_name)

    except Exception as e:
        logger.warning("微信搜索失败(%s): %s", account_name, e)
        # fallback: 返回空列表而非崩溃

    return results[:limit]


def _parse_sogou_weixin_results(html: str, account_name: str) -> list[WechatArticleRef]:
    """从搜狗微信搜索 HTML 中提取文章列表。"""
    from html.parser import HTMLParser

    class SogouParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results: list[WechatArticleRef] = []
            self._in_result = False
            self._in_title = False
            self._in_summary = False
            self._current: dict[str, str] = {}
            self._title_buf = ""
            self._summary_buf = ""

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            cls = attrs_dict.get("class", "")

            if tag == "div" and "txt-box" in cls:
                self._in_result = True
                self._current = {}
            elif self._in_result:
                if tag == "a" and cls == "":
                    href = attrs_dict.get("href", "")
                    if href.startswith("http"):
                        self._current["url"] = href
                    self._in_title = True
                    self._title_buf = ""
                elif tag == "p" and "txt-info" in cls:
                    self._in_summary = True
                    self._summary_buf = ""

        def handle_endtag(self, tag):
            if tag == "a" and self._in_title:
                self._in_title = False
                self._current["title"] = self._title_buf.strip()
            elif tag == "p" and self._in_summary:
                self._in_summary = False
                self._current["summary"] = self._summary_buf.strip()
            elif tag == "div" and self._in_result:
                self._in_result = False
                if self._current.get("title") and self._current.get("url"):
                    self.results.append(WechatArticleRef(
                        title=self._current["title"],
                        url=self._current["url"],
                        summary=self._current.get("summary", ""),
                        account_name=account_name,
                    ))

        def handle_data(self, data):
            if self._in_title:
                self._title_buf += data
            elif self._in_summary:
                self._summary_buf += data

    parser = SogouParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.results


# ── 2. 全文抓取 ──────────────────────────────────────────────────────────


async def fetch_article_content(
    url: str,
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """抓取微信公众号文章的完整内容。

    返回 dict:
    - title: 标题
    - author: 作者
    - account: 公众号名
    - content_html: 正文 HTML
    - content_text: 纯文本
    - images: list[dict]  (url, alt)
    - publish_time: 发布时间
    """
    result: dict[str, Any] = {
        "title": "",
        "author": "",
        "account": "",
        "content_html": "",
        "content_text": "",
        "images": [],
        "publish_time": "",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        ) as client:
            resp = await client.get(url)
            html = resp.text

            # 提取 JSON 数据（微信文章通常在 <script> 里嵌入变量）
            result.update(_extract_weixin_article(html, url))

            # 提取图片
            result["images"] = _extract_images(html, url)

    except Exception as e:
        logger.error("抓取文章失败(%s): %s", url, e)

    return result


def _abs_url(url: str, base: str) -> str:
    """把相对/协议相对 URL 解析为绝对 URL；无法解析则原样返回。"""
    if not url:
        return url
    if url.startswith(("http://", "https://", "data:")):
        return url
    from urllib.parse import urlparse, urljoin

    if url.startswith("//"):
        scheme = urlparse(base).scheme or "https"
        return f"{scheme}:{url}"
    return urljoin(base, url)


def _extract_weixin_article(html: str, url: str) -> dict[str, Any]:
    """从微信文章 HTML 中提取标题、作者、正文等。"""
    from html.parser import HTMLParser

    class WeixinParser(HTMLParser):
        def __init__(self, base_url: str = ""):
            super().__init__()
            self.title = ""
            self.author = ""
            self.account = ""
            self.publish_time = ""
            self.content_parts: list[str] = []
            self._in_content = False
            self._in_script = False
            self._script_buf = ""
            self._depth = 0
            self.base_url = base_url

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "script":
                self._in_script = True
                self._script_buf = ""
            elif tag == "div":
                cls = attrs_dict.get("id", "") or attrs_dict.get("class", "")
                if cls in ("js_content", "rich_media_content", "rich_media_content_inner"):
                    self._in_content = True
                if self._in_content:
                    self._depth += 1
            elif self._in_content:
                # 保留表格结构（用于自动转凭他教育知识卡片）
                if tag in ("table", "thead", "tbody", "tr", "td", "th"):
                    attrs_str = " ".join(
                        f'{k}="{v}"' for k, v in attrs
                        if k.lower() not in ("style", "width", "height", "border")
                    )
                    self.content_parts.append(
                        f"<{tag} {attrs_str}>" if attrs_str else f"<{tag}>"
                    )
                elif tag == "img":
                    # 微信图片常用 data-src，需一并捕获
                    src = attrs_dict.get("data-src") or attrs_dict.get("src") or ""
                    if src:
                        self.content_parts.append(
                            f'<img src="{_abs_url(src, self.base_url)}">'
                        )
                elif tag in ("p", "section", "br"):
                    self.content_parts.append(f"<{tag}>")

        def handle_endtag(self, tag):
            if tag == "script":
                self._in_script = False
                # 尝试从 script 中提取 msg_title 等
                self._parse_vars(self._script_buf)
            elif tag == "div" and self._in_content:
                self._depth -= 1
                if self._depth <= 0:
                    self._in_content = False
            elif self._in_content and tag in ("p", "section", "br"):
                self.content_parts.append(f"</{tag}>")
            elif self._in_content and tag in ("table", "thead", "tbody", "tr", "td", "th"):
                self.content_parts.append(f"</{tag}>")

        def handle_data(self, data):
            if self._in_script:
                self._script_buf += data
            elif self._in_content:
                self.content_parts.append(data)

        def _parse_vars(self, text):
            import json
            # 常见微信文章变量
            for var in ("msg_title", "nickname", "author_name", "ct", "publish_time"):
                pattern = rf'var\s+{var}\s*=\s*["\']([^"\']*)["\']'
                m = re.search(pattern, text)
                if m:
                    val = m.group(1).replace("\\x26lt;", "<").replace("\\x26gt;", ">")
                    if var == "msg_title":
                        self.title = val
                    elif var == "nickname":
                        self.account = val
                    elif var == "author_name":
                        self.author = val
                    elif var in ("ct", "publish_time"):
                        self.publish_time = val

    parser = WeixinParser(url)
    try:
        parser.feed(html)
    except Exception:
        pass

    content_html = "".join(parser.content_parts)
    # 简单去标签得纯文本
    content_text = re.sub(r"<[^>]+>", " ", content_html)
    content_text = re.sub(r"\s+", " ", content_text).strip()

    return {
        "title": parser.title or _fallback_title(html),
        "author": parser.author,
        "account": parser.account,
        "content_html": content_html,
        "content_text": content_text[:20000],  # 截断过长文章
        "publish_time": parser.publish_time,
    }


def _fallback_title(html: str) -> str:
    """从 <title> 或 og:title 提取标题。"""
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'og:title"\s*content="([^"]+)"', html)
    if m:
        return m.group(1).strip()
    return "未知标题"


def _extract_images(html: str, base_url: str) -> list[dict]:
    """提取文章中所有图片 URL（兼容微信 data-src 与常规 src）。"""
    images = []
    seen = set()
    for m in re.finditer(r"<img[^>]+>", html, re.I):
        tag = m.group(0)
        # 微信图片优先用 data-src（懒加载地址），其次 src
        dm = re.search(r'data-src=["\']([^"\']+)["\']', tag, re.I)
        if dm:
            url = dm.group(1)
        else:
            sm = re.search(r'src=["\']([^"\']+)["\']', tag, re.I)
            url = sm.group(1) if sm else ""
        if not url or url.startswith("data:") or url in seen:
            continue
        seen.add(url)
        url = _abs_url(url, base_url)
        alt = ""
        am = re.search(r'alt=["\']([^"\']*)["\']', tag, re.I)
        if am:
            alt = am.group(1)
        images.append({"url": url, "alt_text": alt})
    return images


# ── 3. 内容提炼（不抄袭） ───────────────────────────────────────────────

# 公众号常见噪音（导流语、免责声明等），提炼前先剔除
_NOISE_PATTERNS = [
    r"点击(上方|下方)?[^，。\n]{0,12}关注",
    r"长按(识别|扫描)[^，。\n]{0,20}",
    r"扫码(添加|关注|咨询)[^，。\n]{0,20}",
    r"(本文|素材|图片)?(来源|转载自)[:：][^，。\n]{0,30}",
    r"侵(权|删)[^，。\n]{0,20}",
    r"免责声明[^，。\n]{0,40}",
    r"版权归[^，。\n]{0,30}所有",
    r"欢迎(转发|分享|留言)[^，。\n]{0,20}",
    r"(点个|点击)(在看|赞|关注)[^，。\n]{0,15}",
    r"更多(资讯|信息|内容)[^，。\n]{0,20}",
    r"加(小助手|老师|微信)[^，。\n]{0,20}",
    r"咨询电话[:：]?[\d\-\s]{6,}",
    r"[（(]?文末[^，。\n]{0,20}[)）]?",
]

# 文档式章节标签（如「04 不同的阶段」「提到升学规划」），提炼时剔除
_CHAPTER_LABELS = "不同的阶段|做好升学规划|提到升学规划|怎么做升学规划"
_CHAPTER_NUM_RE = re.compile(r"[\s　]*\d{1,2}[\s　]*(?:" + _CHAPTER_LABELS + r")")
# 作为孤立标签出现的章节词（前后有空白/标点/句尾），无论位置
_CHAPTER_TAG_RE = re.compile(
    r"(?:^|[\s　，。、；：!?！?])(" + _CHAPTER_LABELS + r")(?=[\s　，。、；：!?！?]|$)"
)
_LEADING_NUM_RE = re.compile(r"^\s*\d{1,2}\s+")


def _clean_chapter_markers(text: str) -> str:
    """去掉文档式章节序号与标签（按句处理）。"""
    t = _CHAPTER_NUM_RE.sub(" ", text)
    t = _CHAPTER_TAG_RE.sub("", t)
    t = _LEADING_NUM_RE.sub("", t)
    return re.sub(r"\s{2,}", " ", t).strip()


# 原账号的机构自我介绍/招商宣传：绝不能混进凭他教育的文章里
_PROMO_PATTERNS = [
    r"是一家(专注|致力|专业)",
    r"有限公司|股份公司|集团有限",
    r"(成立于|发起成立|创立于)",
    r"战略合作(伙伴)?关系",
    r"旨在(帮助|为|打造)",
    r"依托[^，。]{0,20}(资源|平台|优势)",
    r"(我们|本公司|本机构|本中心)(是|提供|拥有)",
    r"官方(微信|公众号|网站)",
    r"(报名|咨询|加盟|合作)(热线|方式|请联系)",
    r"(专业平台|服务平台|研究中心)(作为|是)",
    r"提供最新政策解读",
]
_PROMO_RE = re.compile("|".join(_PROMO_PATTERNS))

# 提炼时用于识别"有信息量"的教育领域关键词
_DOMAIN_KEYWORDS = (
    "升学", "规划", "志愿", "填报", "录取", "分数", "位次", "专业", "院校", "大学",
    "高考", "中考", "选科", "招生", "批次", "投档", "强基", "综评", "自主招生",
    "就业", "考研", "保研", "学科", "赋分", "等级", "省控线", "一分一段",
    "家长", "学生", "孩子", "考生", "政策", "改革", "新规", "学区", "分流",
)

_DATA_UNIT_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(%|％|分|名|位|人|万|亿|所|个|年|届|倍|元|천)"
    r"|第\s*\d+\s*(名|位|批)"
    r"|\d{4}\s*年"
)

_CASE_MARKERS = ("例如", "比如", "举例", "案例", "譬如", "以.{2,10}为例", "有位", "有个", "某同学", "某学生")


def _clean_source_text(text: str) -> str:
    """清洗原文：去掉导流语、免责声明、章节标记、多余空白。"""
    cleaned = text
    for pat in _NOISE_PATTERNS:
        cleaned = re.sub(pat, "", cleaned)
    cleaned = _clean_chapter_markers(cleaned)
    cleaned = re.sub(r"[ \t\u3000]+", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()


def _split_into_sentences(text: str) -> list[str]:
    """切成完整句子，保证不出现半截句。"""
    # 在句末标点后插入切分符（保留标点）
    marked = re.sub(r"([。！？!?；;])", lambda m: m.group(1) + "\x00", text)
    raw_parts = re.split(r"[\x00\n]", marked)

    sentences: list[str] = []
    for part in raw_parts:
        s = part.strip()
        if not s:
            continue
        # 去掉行首的序号装饰（01 / 一、 / 1. / ①）
        s = re.sub(r"^\s*(\d{1,2}[、.．)）]|[一二三四五六七八九十]{1,3}[、.]|[①-⑩])\s*", "", s)
        # 去掉文档式章节标签与残留序号
        s = _clean_chapter_markers(s)
        s = s.strip(" -—·•")
        if len(s) < 8:  # 过短片段（多为标题装饰）丢弃
            continue
        sentences.append(s)
    return sentences


def _score_sentence(sentence: str, freq: dict[str, int]) -> float:
    """给句子打分：领域关键词 + 词频 + 长度适中 + 含数据 加权。"""
    score = 0.0
    for kw in _DOMAIN_KEYWORDS:
        if kw in sentence:
            score += 1.6
    # 高频词贡献
    for token, count in freq.items():
        if token in sentence:
            score += min(count, 5) * 0.25
    # 含具体数据的句子更有信息量
    if _DATA_UNIT_PATTERN.search(sentence):
        score += 2.2
    # 长度适中（25-70字）最佳
    n = len(sentence)
    if 25 <= n <= 70:
        score += 1.5
    elif n < 15:
        score -= 1.5
    elif n > 110:
        score -= 1.0
    # 疑问句常为过渡，降权
    if sentence.rstrip().endswith(("？", "?")):
        score -= 0.8
    return score


def _build_freq(sentences: list[str]) -> dict[str, int]:
    """统计中文 2-gram 词频，作为主题词近似。"""
    freq: dict[str, int] = {}
    for s in sentences:
        chars = re.findall(r"[\u4e00-\u9fa5]", s)
        for i in range(len(chars) - 1):
            token = chars[i] + chars[i + 1]
            freq[token] = freq.get(token, 0) + 1
    # 只保留出现 >=3 次的
    return {k: v for k, v in freq.items() if v >= 3}


def _similar(a: str, b: str) -> float:
    """字符级 Jaccard 相似度，用于去重。"""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _pick_diverse(
    scored: list[tuple[float, str]], limit: int, *, sim_threshold: float = 0.62
) -> list[str]:
    """按分数选句，同时保证彼此不重复（MMR 简化版）。"""
    picked: list[str] = []
    for _, sentence in scored:
        if len(picked) >= limit:
            break
        if any(_similar(sentence, p) > sim_threshold for p in picked):
            continue
        picked.append(sentence)
    return picked


def extract_core_content(
    title: str,
    content_text: str,
    account_name: str,
    url: str,
) -> ExtractedCore:
    """从原文提炼核心内容（只做"理解与摘要"，不搬运段落）。

    产出：核心论点 / 关键分论点 / 关键数据 / 典型案例。
    这些是后续重写的"事实骨架"，正文措辞在 rewrite 阶段完全重新组织。
    """
    core = ExtractedCore(
        source_account=account_name,
        source_url=url,
        original_title=title,
    )

    text = _clean_source_text(content_text or "")
    if len(text) < 50:
        return core

    sentences = _split_into_sentences(text)
    if not sentences:
        return core

    # 剔除原账号的机构自述/招商宣传，避免混进凭他教育的文章
    sentences = [s for s in sentences if not _PROMO_RE.search(s)]
    if not sentences:
        return core

    freq = _build_freq(sentences)
    scored = sorted(
        ((_score_sentence(s, freq), s) for s in sentences),
        key=lambda x: x[0],
        reverse=True,
    )

    # ① 核心论点
    core.main_thesis = _summarize_thesis(sentences, title, scored)

    # ② 分论点：取高分且互不重复的句子
    core.key_points = _pick_diverse(scored, 5)

    # ③ 关键数据
    core.key_data = _extract_key_data(sentences)

    # ④ 案例
    core.cases = _extract_cases(sentences)

    return core


def _summarize_thesis(
    sentences: list[str], title: str, scored: list[tuple[float, str]]
) -> str:
    """生成一句话核心论点：优先用标题，其次用最高分句子。"""
    if title:
        clean_title = re.sub(r"[|｜_–—]\s*[^|｜]*$", "", title).strip()
        clean_title = re.sub(r"^[【\[（(][^】\])）]{0,10}[】\])）]\s*", "", clean_title)
        clean_title = clean_title.rstrip("，。；：、：:")
        if len(clean_title) >= 8:
            return clean_title
    if scored:
        return scored[0][1][:60].rstrip("，。；：、：")
    return sentences[0][:60].rstrip("，。；：、：") if sentences else ""


def _extract_key_data(sentences: list[str]) -> list[str]:
    """提取含具体数据的句子（去重、限长）。"""
    out: list[str] = []
    for s in sentences:
        if not _DATA_UNIT_PATTERN.search(s):
            continue
        if len(s) > 90:
            continue
        if any(_similar(s, o) > 0.7 for o in out):
            continue
        out.append(s.rstrip("，。；："))
        if len(out) >= 6:
            break
    return out


def _extract_cases(sentences: list[str]) -> list[str]:
    """提取案例型句子。"""
    out: list[str] = []
    pattern = re.compile("|".join(_CASE_MARKERS))
    for s in sentences:
        if not pattern.search(s):
            continue
        if len(s) < 15 or len(s) > 120:
            continue
        if any(_similar(s, o) > 0.7 for o in out):
            continue
        out.append(s.rstrip("，。；："))
        if len(out) >= 3:
            break
    return out


# ── 4. 重写为凭他教育风格 ────────────────────────────────────────────────

# 同义替换表：把原文措辞换成更专业、学院派的表达，降低雷同度
_PARAPHRASE_MAP = [
    (r"大多数人第一反应是", "不少家长的第一反应是"),
    (r"其实(是)?", "事实上"),
    (r"我们(认为|觉得)", "我们的判断是"),
    (r"你(知道|以为)", "家长常以为"),
    (r"最大的误解", "一个普遍的认知偏差"),
    (r"非常重要", "具有决定性影响"),
    (r"很重要", "不容忽视"),
    (r"需要注意", "值得重点关注"),
    (r"总之", "综合来看"),
    (r"因此", "由此"),
    (r"所以", "因而"),
    (r"但是", "然而"),
    (r"如果", "若"),
    (r"很多", "不少"),
    (r"孩子们", "学生"),
    (r"家长们", "家长"),
    (r"最好", "建议优先"),
    (r"应该", "通常应当"),
    (r"可以", "可考虑"),
]

# 第一/第二人称口语指代 → 中性机构表述
_PRONOUN_MAP = [
    (r"^我们", "凭他教育"),
    (r"小编", "我们"),
    (r"本号", "该账号"),
    (r"关注我们", "持续关注"),
]

# ── 不确定性标注（Word 内渲染为「加粗+下划线」，用户下载后可本地取消）──
_CAUTION_RE = re.compile(r"\[\[CAUTION:(.*?)\]\]", re.DOTALL)
_CAUTION_KEYWORDS = re.compile(
    r"预计|或将|有望|可能|拟|草案|征求意见|计划于|未来|新规|改革|调整|变动|"
    r"据传|网传|业内预测|有望在|据透露|传闻|疑似"
)
_YEAR_RE = re.compile(r"20\d\d\s?年?")


def _wrap_caution(phrase: str) -> str:
    """把「真实性/准确性无法独立核实」的内容标记为需人工复核。"""
    phrase = phrase.strip().rstrip("；;。 ")
    if not phrase:
        return phrase
    return f"[[CAUTION:{phrase}]]"


def _needs_caution(text: str) -> bool:
    """文本是否含政策/前瞻/年份类不确定信息，需要提醒复核。"""
    return bool(_CAUTION_KEYWORDS.search(text)) or bool(_YEAR_RE.search(text))


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _paraphrase(sentence: str) -> str:
    """规则级改写：调整措辞与句式，避免直接照搬原句。"""
    s = sentence.strip()
    for pat, rep in _PRONOUN_MAP:
        s = re.sub(pat, rep, s)
    for pat, rep in _PARAPHRASE_MAP:
        s = re.sub(pat, rep, s)
    # 去掉原文的强营销语气
    s = re.sub(r"[!！]{2,}", "。", s)
    s = s.strip(" ，。；：、")
    return s


def _condense(sentence: str, max_len: int = 46) -> str:
    """压缩成小标题级短句，保证在自然边界断开、不出现半截话。"""
    s = _paraphrase(sentence)
    if len(s) <= max_len:
        return s
    # 在最后一个逗号/顿号处断开
    cut = max(s.rfind("，", 0, max_len), s.rfind("、", 0, max_len), s.rfind("；", 0, max_len))
    if cut >= max_len // 2:
        return s[:cut]
    return s[:max_len]


async def rewrite_article(core: ExtractedCore, settings=None) -> TransformedArticle:
    """把提炼出的事实骨架重写为「凭他生涯」公众号风格的原创文章。

    结构（对齐「凭他生涯」真实推文）：
      张力开头(2段) → 核心定调 → 编号小节(01/02/03 + 加粗小标题 + 数据加粗)
      → 数据一览 → 典型情况参考 → 结尾述评 → 出处标注 → 统一品牌尾注

    若配置了 llm_provider（非 rule）且对应 key 可用，则调用大模型按「凭他生涯」
    文风对正文主体做专业润色/扩写；任一环节失败都回退到本地规则引擎，
    保证离线可用、不依赖任何外部服务。
    """
    title = _generate_title(core)

    main_blocks: list[str] = [
        _build_opening(core),
        _build_thesis(core),
        *_build_body_sections(core),
    ]
    data_block = _build_data_section(core)
    if data_block:
        main_blocks.append(data_block)
    case_block = _build_case_section(core)
    if case_block:
        main_blocks.append(case_block)

    # ── 知识数据卡片（当 card_* 字段有值时自动生成）────────────────
    card_html_fragment = ""
    if core.card_title and core.card_table_headers:
        card_html_fragment = _generate_knowledge_card(core)

    main_block = "\n\n".join(b for b in main_blocks if b and b.strip())

    # 可选：大模型润色（保留规则骨架，仅在可用时增强文采与篇幅）
    if settings is not None and getattr(settings, "llm_provider", "rule") not in ("rule", "none", ""):
        polished = await _polish_article_with_llm(main_block, core, settings)
        if polished:
            main_block = polished

    # 结尾述评 + 出处标注始终由规则生成（确保合规与品牌一致）
    tail_text_blocks = [_build_synthesis(core), _build_source_note(core), _brand_footer_text()]
    main_paras = [p for p in main_block.split("\n\n") if p and p.strip()]

    # 知识卡片嵌入：放在数据区块之后、案例/述评之前
    if card_html_fragment:
        main_paras.append(card_html_fragment)

    body_text = "\n\n".join(main_paras + tail_text_blocks)

    # HTML：主体渲染后追加带样式的品牌尾注 div（导出时按 class 剔除/重排）
    html_paras = main_paras + [_build_synthesis(core), _build_source_note(core)]
    body_html = _render_html(html_paras) + "\n" + _brand_footer_html()

    return TransformedArticle(
        title=title,
        body_text=body_text,
        body_html=body_html,
        source_account=core.source_account,
        source_title=core.original_title,
        source_url=core.source_url,
        word_count=len(re.sub(r"\s", "", body_text)),
    )


async def _polish_article_with_llm(main_block: str, core: ExtractedCore, settings) -> str | None:
    """用大模型按「凭他生涯」文风润色/扩写文章主体；失败返回 None（回退规则）。"""
    system = PINGTA_STYLE_GUIDE
    user = (
        f"原文标题：{core.original_title}\n"
        f"来源账号：{core.source_account}\n\n"
        f"【事实骨架 / 草稿】\n{main_block}\n\n"
        "请在此基础上按「凭他生涯」文风重写扩写为专业公众号文章主体。"
    )
    text = await call_llm(settings, settings.llm_provider, user, system=system, temperature=0.4, timeout=90)
    if not text:
        return None
    # 去掉模型可能包裹的 ```markdown 代码围栏
    text = re.sub(r"^```(?:markdown)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip() or None


def _render_html(paragraphs: list[str]) -> str:
    """把 markdown 风格段落渲染为公众号可用 HTML（含 CAUTION 标注）。"""
    html_parts: list[str] = []
    for para in paragraphs:
        if para.lstrip().startswith("<"):  # 已是 HTML（如品牌尾注）
            html_parts.append(para)
            continue
        lines = para.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 小标题 **xxx**
            m = re.fullmatch(r"\*\*(.+?)\*\*", line)
            if m:
                html_parts.append(
                    f'<h3 style="font-size:17px;font-weight:600;color:#1a3d6d;'
                    f'margin:22px 0 10px;">{m.group(1)}</h3>'
                )
                continue
            # 行内加粗
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            # 不确定性标注 → 下划线+加粗（提醒人工复核）
            line = _CAUTION_RE.sub(
                r'<span style="text-decoration:underline;font-weight:bold;'
                r'color:#9a2b2b;">\1</span>',
                line,
            )
            html_parts.append(
                f'<p style="font-size:15px;line-height:1.85;color:#333;'
                f'margin:0 0 14px;">{line}</p>'
            )
    return "\n".join(html_parts)


# ── 凭他生涯写作风格（基于真实推文逆向提炼） ──────────────────────────────
#
# 标题：年份+地域+核心主题｜副标题（数字/对比/疑问）
#   例：「江苏2026高考"尖子生地图"｜物理前10000名考生如何选择985、211？」
#       「2026江苏高考新风向｜4大专业暴涨、4大专业遇冷，4类专业迎来黄金期！」
# 开头：①张力/对比钩子 ②"凭他教育汇总整理了…一起来看看…"建立权威并邀请阅读
# 正文：编号小节（01/02/03）+ 加粗小标题 + 要点/列表 + 关键数据加粗 + ⚠️/❗️提示框
# 声音：直接对家长说话（"建议2027届考生及家长重点关注"），规划师人设，数据+解读
# 结尾：综合述评段落 + 统一品牌尾注（关注【凭他教育】… + 服务推广）
# 严禁：泛泛的"核心结论/行动建议"标签、与样例不符的学院派空话。

PINGTA_STYLE_GUIDE = (
    "你是「凭他教育」——常州本地专业高考升学规划机构「凭他生涯」公众号的资深内容主编。\n"
    "请严格按以下「凭他生涯」真实文风重写文章主体：\n"
    "1) 标题：采用「年份+地域+核心主题｜副标题」结构，副标题用数字/对比/疑问制造钩子，"
    "例如『江苏2026高考\"尖子生地图\"｜物理前10000名考生如何选择985、211？』。\n"
    "2) 开头两段：第一段用张力或对比制造钩子（如'每年…呼声不绝于耳，可…'）；"
    "第二段以『凭他教育汇总整理了…数据/情况，一起来看看…』承接，建立权威并邀请家长阅读。\n"
    "3) 正文：用 01/02/03 编号小节，每节一个加粗短句小标题；多用要点列表；"
    "所有关键数据、分数、位次、百分比一律加粗；适当用 ⚠️注意 / ❗️需要注意的是 提示框。\n"
    "4) 声音：直接对家长说话（'建议考生及家长重点关注…'），保持规划师专业人设，"
    "对数据做'为什么'的解读，而非只堆数据。\n"
    "5) 结尾：一段'综合来看/写在最后'的述评，自然带出可落地的建议；不要出现"
    "『核心结论』『行动建议』这类标签。\n"
    "6) 对来源不确定、年份未定、或'约/预计/新规'类的数据与政策，必须用 [[CAUTION:…]] 包裹。\n"
    "7) 不编造具体人名、院校录取分数线等无法核实的事实；"
    "只输出文章主体（不要标题、不要品牌尾注），markdown 纯文本，正文 1200-1600 字。"
)


def _extract_year(text: str) -> str:
    m = _YEAR_RE.search(text or "")
    return m.group(0).replace(" ", "") if m else ""


def _topic_phrase(core: ExtractedCore) -> str:
    """取干净的主题短语：优先用原标题（更短更干净），回退核心论点。"""
    src = core.original_title or core.main_thesis or "升学动态"
    topic = _condense(src, 22).strip("：:，。；、—-")
    topic = re.sub(r"[|｜_–—].*$", "", topic).strip()   # 去掉原标题可能带的副标题
    topic = re.sub(r"^20\d\d\s?", "", topic)              # 避免与前置年份重复
    if not topic:
        topic = _condense(core.main_thesis or "升学动态", 18)
    return topic


def _generate_title(core: ExtractedCore) -> str:
    """生成「凭他生涯」风格标题：年份+主题｜副标题（数字/对比/疑问）。"""
    year = _extract_year(" ".join(core.key_data) + " " + (core.main_thesis or ""))
    topic = _topic_phrase(core)

    subtitle = ""
    # 优先用一条最抓眼球的数据做副标题
    for d in core.key_data:
        if _DATA_UNIT_PATTERN.search(d) and len(d) <= 40:
            subtitle = _condense(d, 30).rstrip("；;。 ")
            break
    # 其次用多个要点构成"N大看点"
    if not subtitle and len(core.key_points) >= 2:
        subtitle = f"{len(core.key_points)}大核心看点，家长提前掌握"
    # 再退化为设问
    if not subtitle:
        subtitle = "考生和家长该如何应对？"

    if year:
        return f"{year}{topic}｜{subtitle}"
    return f"{topic}｜{subtitle}"


def _build_opening(core: ExtractedCore) -> str:
    """开头两段：张力钩子 + 凭他教育整理邀请（对齐凭他生涯开篇）。"""
    import random

    topic = _topic_phrase(core)
    hook_templates = [
        f"每到升学季，关于「{topic}」的讨论就格外热烈，可真正能指导志愿决策的硬信息，"
        f"却常被淹没在碎片化的资讯里。",
        f"「{topic}」看似老生常谈，但放到今年的招录格局里，不少家庭的认知还停留在两三年前。",
        f"分数一年更比一年卷，可真正决定去向的，往往不是那几十分，而是对「{topic}」的提前理解。",
    ]
    hook = random.choice(hook_templates)
    bridge = (
        f"凭他教育汇总整理了相关公开信息与最新数据，结合常州及江苏本地的实际情况，"
        f"为大家做一期系统拆解——低年级学生和家长可以重点参考，提前规划不迷路。"
    )
    return f"{hook}\n\n{bridge}"


def _build_thesis(core: ExtractedCore) -> str:
    """核心定调：融入开头后的首段结论，不单独打「核心结论」标签。"""
    thesis = _paraphrase(core.main_thesis or core.original_title)
    return (
        f"先给结论：**{thesis}**。"
        f"在凭他教育看来，这本质上不是“选哪所学校”的孤立判断，"
        f"而是信息、位次与路径设计三者之间的动态平衡——先把结构看清楚，再做选择才不会被动。"
    )


# 凭他生涯式展开开头词（贴近其"数据+解读"口吻）
_INTERP_OPENERS = [
    "从数据可以看出，",
    "这意味着，",
    "需要提醒家长的是，",
    "换个角度看，",
    "结合近年趋势，",
]
# 凭他生涯式收尾建议（直接对家长说话）
_ADVICE_TAILS = [
    "建议相关年级考生及家长重点关注，尽早规划对应路径。",
    "建议家长结合孩子实际位次与选科，提前把这条路径纳入备选。",
    "这一点，低年级家庭尤其要早做打算，避免临到高三才补救。",
]
_PRINCIPLES = [
    "平行志愿投档遵循“分数优先、遵循志愿、一轮投档”的原则，理解这一机制是避免滑档的前提。",
    "院校层次、学科实力与地域资源三者往往难以兼得，取舍的优先级应服务于孩子的长期发展。",
    "一分一段表是把“分数”翻译成“位次”的关键工具，位次比绝对分数更能反映竞争格局。",
    "专业组模式下，调剂风险从“院校内”细化到“专业组内”，填报时需逐组核对选考要求。",
    "升学规划不是出分后的临时动作，而应从高一开始做信息与路径的持续积累。",
    "政策口径具有年度差异性，任何跨年引用都应以当年省级招考机构发布的原文为准。",
]


def _build_body_sections(core: ExtractedCore) -> list[str]:
    """编号小节（01/02/03）+ 加粗小标题 + 要点展开，对齐凭他生涯排版。"""
    sections: list[str] = []
    for i, point in enumerate(core.key_points[:5], 1):
        heading = _condense(point, 30).rstrip("：:，。；、—-")
        if len(heading) < 6:
            heading = _condense(point, 22).rstrip("：:，。；、—-")
        body = _elaborate(point, core, i - 1)
        sections.append(f"**{i:02d}**\n\n**{heading}**\n\n{body}")
    return sections


def _elaborate(point: str, core: ExtractedCore, idx: int) -> str:
    """把一个要点展开为凭他生涯式论述：陈述 + 解读 + 数据加粗 + 家长建议。"""
    clean = _paraphrase(point)
    if _needs_caution(clean):
        clean = _wrap_caution(clean)
    opener = _INTERP_OPENERS[idx % len(_INTERP_OPENERS)]
    para1 = f"{opener}{clean}。"

    # 嵌入一条相关数据，加粗并标注待复核
    related = [d for d in core.key_data if _jaccard(clean, d) > 0.12]
    para2 = ""
    if related:
        para2 = (
            f"公开数据中可见：**{_wrap_caution(_paraphrase(related[0]))}**"
            f"——具体口径请以官方当年发布为准。"
        )
    elif _PRINCIPLES:
        para2 = _PRINCIPLES[idx % len(_PRINCIPLES)]

    tail = _ADVICE_TAILS[idx % len(_ADVICE_TAILS)]
    return "\n\n".join([p for p in (para1, para2, tail) if p])


def _build_data_section(core: ExtractedCore) -> str:
    """数据一览（每条关键数据加粗并标注待复核，不编造）。"""
    if not core.key_data:
        return ""
    lines = ["**数据一览（发布前请人工复核）**", ""]
    for d in core.key_data[:6]:
        lines.append(f"· **{_wrap_caution(_paraphrase(d))}**；")
    lines.append("")
    lines.append(
        "说明：以上数据引自公开报道或第三方整理，年份与统计口径可能与官方发布存在差异；"
        "正式用于个案建议前，请凭他教育顾问以省级教育考试院 / 院校招生网当年权威发布交叉核验。"
    )
    return "\n".join(lines)


def _build_case_section(core: ExtractedCore) -> str:
    """典型情况参考（姓名脱敏，符合 V2.0 规范）。"""
    if not core.cases:
        return ""
    lines = ["**典型情况参考**", ""]
    for c in core.cases[:2]:
        desensitized = re.sub(r"([\u4e00-\u9fa5]{1,2})(同学|学生|家长)", r"某\2", _paraphrase(c))
        lines.append(f"· {desensitized}。")
    return "\n".join(lines)


def _build_synthesis(core: ExtractedCore) -> str:
    """结尾述评：综合来看 + 自然建议，不用「行动建议」标签。"""
    topic = _topic_phrase(core)
    return (
        f"综合来看，围绕「{topic}」，信息的及时与准确，往往比一时的分数更影响最终的去向。"
        f"无论是冲击顶尖高校，还是稳妥锁定理想专业，最重要的一条逻辑始终是："
        f"以高考成绩为核心，以强基计划、综合评价等多元路径为辅助，"
        f"在不影响主线的前提下提前准备、精准匹配。"
        f"凭他教育会持续关注江苏及常州的升学动态，第一时间为家长带来可落地的拆解与分析。"
    )


def _build_source_note(core: ExtractedCore) -> str:
    """出处标注：合规、透明，声明为二次创作。"""
    src = core.source_account or "公开渠道"
    return (
        f"*本文基于「{src}」公开发布内容的核心信息，"
        f"由凭他教育团队重新梳理、核实并成稿；文中带下划线 / 加粗处为尚待权威来源复核的内容，"
        f"正式发布前请务必确认其真实性。*"
    )


def _generate_knowledge_card(core: ExtractedCore) -> str:
    """从 core.card_* 字段生成凭他教育知识数据卡片 HTML 片段（嵌入文章用）。

    返回的 HTML 可直接插入 body_html（公众号富文本）和 body_text（作为占位标记）。
    卡片样式完全对齐凭他生涯公众号真实发文（深蓝+金、统计栏、表格、品牌尾注）。
    支持两种模式：
    - 结构化数据模式：用 render_fragment() 渲染标准卡片（表头+数据行）
    - 视觉包装模式（_is_visual_wrapper）：把清理后的表格图片嵌入卡片框架内
    """
    try:
        # 检测是否为视觉包装模式（图片表格无法 OCR 时的兜底）
        is_visual_wrapper = bool(getattr(core, '_card_is_visual_wrapper', False))
        # 从 core 的附加属性检测（通过 card_rows 中的 __IMAGE_TABLE__ 标记）
        img_src = None
        for r in (core.card_table_rows or []):
            if r and len(r) > 0 and str(r[0]).startswith("__IMAGE_TABLE__:"):
                img_src = str(r[0])[len("__IMAGE_TABLE__:"):]
                is_visual_wrapper = True
                break

        if is_visual_wrapper and img_src:
            return _render_visual_wrapper_card(core, img_src)

        # 标准结构化数据卡片
        card = build_card_from_data(
            title=core.card_title,
            subtitle=core.card_subtitle,
            stat_items=core.card_stats or [],
            table_title=core.card_table_title or "数据详情",
            table_headers=core.card_table_headers,
            table_rows=core.card_table_rows,
        )
        return card.render_fragment()
    except Exception as e:
        logger.warning("知识卡片生成失败（回退为普通表格）: %s", e)
        # 降级：输出一个简单的 markdown 表格
        return _fallback_table_html(core)


def _render_visual_wrapper_card(core: ExtractedCore, img_src: str) -> str:
    """渲染视觉包装模式的卡片：把表格图片嵌入凭他教育知识卡片框架。"""
    # 使用作用域安全 CSS（不含全局 * / body 规则，避免污染父页面布局）
    card_css = KnowledgeCard._style_block_scoped()
    # _style_block_scoped() 返回裸 CSS（无 <style> 标签），必须手动包裹
    style_tag = f"<style>\n{card_css}\n</style>"

    stats_html = ""
    if core.card_stats:
        parts = []
        for s in core.card_stats[:3]:
            label = s.get("label", "")
            value = s.get("value", "")
            unit = s.get("unit", "")
            parts.append(
                f'<div class="pc-stat">'
                f'  <div class="pc-stat-label">{label}</div>'
                f'  <div class="pc-stat-value-wrap">'
                f'    <span class="pc-stat-num">{value}</span>'
                f'    <span class="pc-stat-unit">{unit}</span>'
                f'  </div></div>'
            )
        stats_html = f'<div class="pc-stats">{"  ".join(parts)}</div>'

    table_title = core.card_table_title or "数据明细"
    table_area = (
        f'<div class="pc-table-wrap">'
        f'  <div class="pc-table-head"><span class="star">★</span> '
        f'{table_title} <span class="star">★</span></div>'
        f'  <div style="padding:8px;text-align:center;background:#FFFFFF;">'
        f'    <img src="{img_src}" style="max-width:100%;border-radius:4px;" />'
        f'  </div></div>'
    )

    # 使用 knowledge_card 的图标 SVG
    cap_svg = KnowledgeCard._ICON_GRAD_CAP.format(navy=C_NAVY, gold=C_GOLD)
    temple_svg = KnowledgeCard._ICON_TEMPLE.format(gold=C_GOLD)

    card_html = (
        f'<div class="pc-card">'
        f'  <div class="pc-corner-tl"></div><div class="pc-corner-tr"></div>'
        f'  <div class="pc-corner-bl"></div><div class="pc-corner-br"></div>'
        f'  <div class="pc-wm"></div>'
        f'  <div class="pc-header">'
        f'    <div class="pc-cap">{cap_svg}</div>'
        f'    <div class="pc-header-text">'
        f'      <div class="pc-title">{core.card_title or "数据一览"}</div>'
        f'      <div class="pc-subtitle">{core.card_subtitle or ""}</div>'
        f'    </div></div>'
        f'  {stats_html}'
        f'  {table_area}'
        f'  <div class="pc-footer">'
        f'    <div>{temple_svg}</div>'
        f'    <span class="pc-footer-star">★</span>'
        f'    <span class="pc-footer-text">凭他教育升学规划整体解决方案</span>'
        f'    <span class="pc-footer-star">★</span>'
        f'    <span class="pc-footer-sub">公众号 常州家长荟</span>'
        f'  </div></div>'
    )

    # 返回：style标签 + 卡片HTML（确保 style 在前，_render_html 会原样透传以 < 开头的段落）
    return f"{style_tag}\n{card_html}"


def _fallback_table_html(core: ExtractedCore) -> str:
    """卡片生成异常时的降级：输出简洁 HTML 表格。"""
    if not core.card_table_headers:
        return ""
    lines = ['<table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;">']
    th_line = "<tr>" + "".join(
        f'<th style="border:1px solid #C9A96E;padding:8px;background:#1B2A4A;color:#E8E4DB;">{h}</th>'
        for h in core.card_table_headers
    ) + "</tr>"
    lines.append(th_line)
    for row in (core.card_table_rows or [])[:20]:
        td_line = "<tr>" + "".join(
            f'<td style="border:1px solid #C9A96E;padding:7px;text-align:center;">{c}</td>'
            for c in row
        ) + "</tr>"
        lines.append(td_line)
    lines.append("</table>")
    return "\n".join(lines)


def _brand_footer_html() -> str:
    """底部品牌文案（对齐「凭他生涯」真实文末排版），用 class 便于导出时识别。"""
    return (
        '<div class="pingta-brand-footer">'
        f'<p style="text-align:center;color:#1a3d6d;font-size:15px;font-weight:600;'
        f'margin:24px 0 8px;">关注【{BRAND_NAME}】{BRAND_SLOGAN}</p>'
        f'<p style="text-align:center;color:#666;font-size:13px;line-height:1.7;'
        f'margin:0 0 18px;">{BRAND_PROMO}</p>'
        "</div>"
    )


def _brand_footer_text() -> str:
    """底部品牌文案的纯文本版本（用于 Word 导出与 body_text）。"""
    return f"关注【{BRAND_NAME}】{BRAND_SLOGAN}\n{BRAND_PROMO}"


# ── 5. 图片水印处理 ────────────────────────────────────────────────────


async def process_image_with_watermark(
    image_url: str,
    *,
    output_dir: str | None = None,
    timeout: float = 15.0,
) -> tuple[bytes | None, str]:
    """下载图片 → 去原水印（尽力）→ 叠加凭他教育水印 → 返回 (bytes, mime_type)。"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            img_bytes = resp.content
    except Exception as e:
        logger.warning("下载图片失败(%s): %s", image_url[:80], e)
        return None, ""

    return await asyncio.to_thread(_apply_watermark_to_bytes, img_bytes)


def _apply_watermark_to_bytes(img_bytes: bytes) -> tuple[bytes, str]:
    """对图片字节施加凭他教育水印（同步 CPU 密集操作）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(__import__("io").BytesIO(img_bytes)).convert("RGBA")

        # 创建水印层
        watermark = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)

        # 字体（回退到默认）
        font_size = max(int(min(img.size) * 0.06), 20)
        try:
            font = ImageFont.truetype(
                "/System/Library/Fonts/PingFang.ttc", font_size
            )
        except (IOError, OSError):
            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/STHeiti Light.ttc", font_size
                )
            except (IOError, OSError):
                font = ImageFont.load_default()

        # 计算铺满画布的水印位置
        text = WATERMARK_TEXT
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin_x, margin_y = tw * 1.5, th * 1.5

        # RGBA 水印色（深灰半透明）
        rgba = (60, 60, 60, int(255 * WATERMARK_ALPHA))

        for y in range(-int(img.size[1] / th) * th + 10, img.size[1] + th, int(margin_y)):
            for x in range(-int(img.size[0] / tw) * tw, img.size[0] + tw, int(margin_x)):
                # 旋转文字需先写到临时图层再旋转粘贴
                txt_img = Image.new("RGBA", (tw + 20, th + 20), (255, 255, 255, 0))
                txt_draw = ImageDraw.Draw(txt_img)
                txt_draw.text((10, 10), text, font=font, fill=rgba)
                rotated = txt_img.rotate(WATERMARK_ANGLE, expand=True)
                watermark.paste(rotated, (x, y), rotated)

        # 合成
        watermarked = Image.alpha_composite(img, watermark).convert("RGB")

        # 输出为 bytes
        buf = __import__("io").BytesIO()
        watermarked.save(buf, format="PNG", quality=95)
        return buf.getvalue(), "image/png"

    except ImportError:
        logger.warning("Pillow 未安装，跳过图片水印处理")
        return img_bytes, "image/png"
    except Exception as e:
        logger.error("图片水印处理失败: %s", e)
        return img_bytes, "image/png"


# ── 6. 表格水印处理 ────────────────────────────────────────────────────


def apply_table_watermark(table_html: str) -> str:
    """对表格 HTML 施加「凭他教育」防盗水印标注。

    V2.0 规范：表格内部均匀铺设斜向水印。
    实际输出时在前端 CSS 层实现（background-image + repeat），
    此处返回带水印样式类的 HTML。
    """
    if not table_html.strip():
        return table_html

    # 包装一层带水印背景的 div
    wrapped = (
        f'<div class="pingta-watermarked-table" '
        f'style="'
        f'position:relative;'
        f'background-image:url(\'data:image/svg+xml;base64,{_watermark_svg_base64()}\');'
        f'background-repeat:repeat;'
        f'background-size:180px 80px;"'
        f'>{table_html}</div>'
    )
    return wrapped


def _watermark_svg_base64() -> str:
    """生成斜向水印 SVG 的 base64。"""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="200" height="100" viewBox="0 0 200 100">'
        f'<text x="50%" y="50%" fill="rgba(0,0,0,{WATERMARK_ALPHA})" '
        f'font-size="16" font-family="sans-serif" '
        f'transform="rotate(-30 100 50)" text-anchor="middle"'
        f'>{WATERMARK_TEXT}</text></svg>'
    )
    import base64 as b64
    return b64.b64encode(svg.encode()).decode()


# ── 7. 主流程编排 ────────────────────────────────────────────────────────

from collections import OrderedDict  # noqa: E402

# 转化结果缓存：导出 Word/HTML 时直接复用，避免重复抓取（解决下载慢的问题）
_TRANSFORM_CACHE: "OrderedDict[str, TransformedArticle]" = OrderedDict()
_TRANSFORM_CACHE_MAX = 30


def _cache_put(url: str, article: "TransformedArticle") -> None:
    _TRANSFORM_CACHE[url] = article
    while len(_TRANSFORM_CACHE) > _TRANSFORM_CACHE_MAX:
        _TRANSFORM_CACHE.popitem(last=False)


def get_cached_article(url: str) -> "TransformedArticle | None":
    """导出时优先取缓存（毫秒级）；缓存未命中再回退到实时转化。"""
    return _TRANSFORM_CACHE.get(url)


def _extract_table_data(table_html: str) -> tuple[list[str], list[list[str]]]:
    """从原表解析出表头与数据行（去掉原表样式/水印，仅保留文本）。"""
    def _cells(row_html: str) -> list[str]:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL | re.IGNORECASE)
        out = []
        for c in cells:
            c = re.sub(r"<[^>]+>", "", c)        # 去标签
            c = re.sub(r"&[a-z]+;", "", c)        # 去实体
            c = re.sub(r"\s+", " ", c).strip()
            out.append(c)
        return out

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
    if not rows:
        return [], []
    matrix = [_cells(r) for r in rows]
    headers = matrix[0] if matrix else []
    body = matrix[1:] if len(matrix) > 1 else []
    return headers, body


def _build_our_table_html(headers: list[str], rows: list[list[str]]) -> str:
    """用原表数据生成「凭他教育」自己的干净表格（去除原水印 + 加凭他水印）。"""
    if not headers and not rows:
        return ""
    wm = _watermark_svg_base64()
    cols = max([len(headers)] + [len(r) for r in rows]) or 1
    thead = ""
    if headers:
        cells = "".join(
            f'<th style="border:1px solid #d9cdb0;padding:8px 10px;background:#1a3d6d;'
            f'color:#fff;font-weight:600;">{h}</th>'
            for h in headers[:cols]
        )
        thead = f"<thead><tr>{cells}</tr></thead>"
    body_rows = ""
    for r in rows:
        cells = "".join(
            f'<td style="border:1px solid #e3ddcf;padding:8px 10px;">'
            f'{r[c] if c < len(r) else ""}</td>'
            for c in range(cols)
        )
        body_rows += f"<tr>{cells}</tr>"
    tbody = f"<tbody>{body_rows}</tbody>"
    return (
        f'<div style="position:relative;margin:16px 0;'
        f'background-image:url(\'data:image/svg+xml;base64,{wm}\');'
        f'background-repeat:repeat;background-size:200px 100px;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;'
        f'background:rgba(255,255,255,0.86);">{thead}{tbody}</table>'
        f'<div style="text-align:right;font-size:11px;color:#9a8f76;margin-top:4px;">凭他教育整理</div>'
        f"</div>"
    )


async def transform_article(
    article_url: str,
    account_name: str = "",
) -> TransformedArticle:
    """完整转化流程：抓取 → 提炼 → 重写 → 水印。

    这是外部调用的唯一入口。
    """
    # Step 1: 抓取全文
    raw = await fetch_article_content(article_url)

    # 抓取失败 / 内容过短（如文章需登录、已删除、反爬拦截）→ 明确报错，避免产出伪稿
    content_text = (raw.get("content_text") or "").strip()
    if len(content_text) < 120:
        raise ValueError(
            "未能从该链接抓取有效正文：请确认链接为有效的 mp.weixin.qq.com 文章，"
            "且文章未设置登录可见或已被删除。"
        )

    # Step 2: 提炼核心
    core = extract_core_content(
        title=raw.get("title", ""),
        content_text=raw.get("content_text", ""),
        account_name=raw.get("account") or account_name,
        url=article_url,
    )

    # Step 3: 解析文章内表格（HTML 表格 → 知识卡片）
    tables_html = re.findall(
        r"<table[^>]*>.*?</table>", raw.get("content_html", ""), re.DOTALL
    )
    our_tables: list[ArticleTable] = []
    for t in tables_html:
        h, b = _extract_table_data(t)
        if not h and not b:
            continue
        our_tables.append(ArticleTable(headers=h, rows=b, html=_build_our_table_html(h, b)))

    # 优先用 HTML 表格自动生成凭他教育知识卡片
    card_fields: dict | None = None
    if our_tables:
        card_fields = _table_to_card_fields(our_tables[0], raw.get("title", ""))

    # Step 4: 处理图片——下载 → 去水印 → （若配视觉模型）OCR 成卡片 → （无OCR则包装进卡片框架）
    cleaned_images: list[tuple[bytes, str, str]] = []  # (bytes, mime, url)
    vision_cfg = _resolve_vision_config(get_settings())
    # 收集可能包含表格的图片（宽>高 或 大尺寸），用于后续卡片包装
    table_like_images: list[tuple[bytes, str, str]] = []
    for img_dict in raw.get("images", []):
        img_url = img_dict.get("url", "")
        if not img_url:
            continue
        img_bytes, mime = await _download_image(img_url)
        if not img_bytes:
            continue
        # 自动选择最佳去水印策略（NLM 双通道去噪为主）
        clean_bytes = _remove_watermark_bytes(img_bytes, method="auto")
        # 判断是否像表格图片（用于后续卡片包装）
        _is_table_like = _looks_like_table_image(clean_bytes)
        if _is_table_like:
            table_like_images.append((clean_bytes, mime or "image/jpeg", img_url))
        # 视觉模型把图片表格 OCR 成结构化数据 → 知识卡片（仅在尚未有 HTML 表格卡片时）
        if vision_cfg and card_fields is None:
            ocr = await _extract_table_from_image_via_vision(clean_bytes, mime, vision_cfg)
            if ocr:
                card_fields = ocr
        cleaned_images.append((clean_bytes, mime or "image/jpeg", img_url))

    # 把卡片字段写回 core，让 rewrite_article 自动渲染知识卡片
    if card_fields:
        core.card_title = card_fields.get("title", "")
        core.card_subtitle = card_fields.get("subtitle", "")
        core.card_stats = card_fields.get("stats", []) or []
        core.card_table_title = card_fields.get("table_title", "")
        core.card_table_headers = card_fields.get("headers", []) or []
        core.card_table_rows = card_fields.get("rows", []) or []
    elif table_like_images and not our_tables:
        # 无 HTML 表格、无视觉 OCR，但有疑似表格图片 → 包装进知识卡片视觉框架
        best_img = _pick_best_table_image(table_like_images) or table_like_images[0]
        card_fields = _build_visual_card_wrapper(core, best_img)
        # 关键：必须写回 core，否则 rewrite_article 拿不到数据
        if card_fields:
            core.card_title = card_fields.get("title", "")
            core.card_subtitle = card_fields.get("subtitle", "")
            core.card_stats = card_fields.get("stats", []) or []
            core.card_table_title = card_fields.get("table_title", "")
            core.card_table_headers = card_fields.get("headers", []) or []
            core.card_table_rows = card_fields.get("rows", []) or []

    # Step 5: 重写（配置了 llm_provider 时尝试大模型润色，失败自动回退规则）
    article = await rewrite_article(core, settings=get_settings())
    article.tables = our_tables

    # Step 6: 把去水印后的原图嵌入正文（未被转成卡片的图片），满足"去掉原本水印"诉求
    article.body_html = _embed_cleaned_images(
        article.body_html, cleaned_images, card_used=bool(card_fields)
    )
    article.images = [
        ArticleImage(
            url=url, alt_text="", processed_data=data, processed_mime=mime
        )
        for data, mime, url in cleaned_images
    ]

    # 写入缓存，供导出时秒级复用（解决 Word 下载慢）
    _cache_put(article_url, article)

    logger.info(
        "文章转化完成: %s → %s (%d字, %d图, %d表, 卡片=%s)",
        core.original_title[:30], article.title, article.word_count,
        len(cleaned_images), len(our_tables), bool(card_fields),
    )

    return article


def _embed_processed_images(html: str, images: list[ArticleImage]) -> str:
    """将处理后的图片（base64）嵌入 HTML 替换原图。"""
    for i, img in enumerate(images):
        if img.processed_data:
            b64 = base64.b64encode(img.processed_data).decode()
            src = f"data:{img.processed_mime};base64,{b64}"
            # 替换第一个匹配的 img src（简单策略）
            if i == 0:
                html = re.sub(
                    r'<img[^>]*src=["\'][^"\']*["\']',
                    f'<img src="{src}" style="max-width:100%;"',
                    html,
                    count=1,
                )
    return html


# ── 7.5 表格 → 知识卡片 / 图片 OCR 辅助 ────────────────────────────────────


def _resolve_vision_config(settings) -> dict | None:
    """解析视觉模型配置（复用 llm_client 的 _resolve_config）。未配置则返回 None。"""
    provider = getattr(settings, "vision_llm_provider", "") or ""
    if not provider:
        return None
    # _resolve_config 接受 provider 名；其前缀逻辑读取 {provider}_api_key 等
    from app.services.llm_client import _resolve_config

    cfg = _resolve_config(settings, provider)
    return cfg


def _table_to_card_fields(
    table: ArticleTable, article_title: str
) -> dict | None:
    """把解析出的 HTML 表格转成知识卡片所需字段（标题/副标题/统计/表头/表行）。

    统计栏按列语义自动推断：人数(求和) / 高中·学校(去重计数) / 专业(去重计数) / 条目数。
    """
    headers = table.headers
    rows = table.rows
    if not headers and not rows:
        return None

    # 定位语义列
    def _col_index(keywords: list[str]) -> int:
        for kw in keywords:
            for i, h in enumerate(headers):
                if kw in (h or ""):
                    return i
        return -1

    name_col = _col_index(["高中", "学校", "中学", "学院", "单位", "地区", "城市", "姓名"])
    major_col = _col_index(["专业", "方向", "学科", "类别"])
    count_col = _col_index(["人数", "录取", "计划", "名额", "数量", "总数", "合计"])

    stats: list[dict] = []
    # 条目数（数据行数）永远有
    stats.append({"label": "条目数", "value": str(len(rows)), "unit": "条"})
    if name_col >= 0:
        distinct = len({r[name_col] for r in rows if r and r[name_col]})
        if distinct:
            stats.append({"label": "涉及" + (headers[name_col] or "对象"), "value": str(distinct), "unit": "个"})
    if major_col >= 0:
        distinct = len({r[major_col] for r in rows if r and r[major_col]})
        if distinct:
            stats.append({"label": "涉及" + (headers[major_col] or "专业"), "value": str(distinct), "unit": "个"})
    if count_col >= 0:
        nums = []
        for r in rows:
            if r and r[count_col]:
                m = re.search(r"\d+", r[count_col])
                if m:
                    nums.append(int(m.group()))
        if nums:
            stats.append({"label": (headers[count_col] or "总数"), "value": str(sum(nums)), "unit": "人"})
    # 最多取 3 个统计
    stats = stats[:3]

    # 标题/副标题：取文章标题的可读部分
    title = (article_title or "数据一览").split("｜")[0].split("|")[0].strip()
    title = title[:18] if title else "数据一览"
    subtitle = "数据明细"
    if len(headers) >= 2:
        subtitle = f"{headers[0]}·{headers[-1]}一览" if headers[0] != headers[-1] else f"{headers[0]}一览"

    return {
        "title": title,
        "subtitle": subtitle,
        "stats": stats,
        "table_title": "数据明细",
        "headers": headers,
        "rows": rows,
    }


async def _download_image(url: str, timeout: float = 15.0) -> tuple[bytes | None, str]:
    """下载图片字节，返回 (bytes, mime)。失败返回 (None, \"\")。"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "image/jpeg")
    except Exception as e:
        logger.warning("下载图片失败(%s): %s", url[:80], e)
        return None, ""


def _remove_watermark_bytes(img_bytes: bytes, method: str = "auto") -> bytes:
    """去原水印，返回清理后的字节（失败回退原图）。auto 模式自动选择最优策略。"""
    import cv2
    import numpy as np

    arr = np.frombuffer(img_bytes, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return img_bytes
    try:
        res = remove_watermark(bgr, method=method, min_confidence=0.06)
        if res.image is not None:
            ok, buf = cv2.imencode(".jpg", res.image, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if ok:
                return buf.tobytes()
    except Exception as e:
        logger.warning("去水印失败，回退原图: %s", e)
    return img_bytes


_VISION_TABLE_PROMPT = """这是一张包含数据表格的图片（可能是录取名单、分数表、统计表等）。
请识别其中的表格，并以 JSON 返回：
{
  "title": "表格主题(如校名/地区)",
  "subtitle": "副标题(如年份+录取类型)",
  "stats": [{"label":"统计项","value":"数值","unit":"单位"}],
  "table_title": "表格区域标题",
  "headers": ["列1","列2"],
  "rows": [["单元格1","单元格2"]]
}
要求：只返回 JSON，不要解释；姓名按原文脱敏保留（如 张**）；数字必须来自图片真实内容；若图片不是表格则返回 {"not_table": true}。"""


async def _extract_table_from_image_via_vision(
    img_bytes: bytes, mime: str, cfg: dict
) -> dict | None:
    """用视觉模型把图片表格 OCR 成结构化数据；不是表格或失败则返回 None。"""
    settings = get_settings()
    provider = getattr(settings, "vision_llm_provider", "") or ""
    text = await call_vision_llm(
        settings, provider, _VISION_TABLE_PROMPT,
        image_bytes=img_bytes, image_mime=mime or "image/jpeg",
    )
    if not text:
        return None
    # 提取 JSON
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        import json
        data = json.loads(m.group(0))
    except Exception:
        return None
    if data.get("not_table"):
        return None
    if not data.get("headers") or not data.get("rows"):
        return None
    return {
        "title": data.get("title", "数据一览"),
        "subtitle": data.get("subtitle", ""),
        "stats": data.get("stats", []) or [],
        "table_title": data.get("table_title", "数据明细"),
        "headers": data.get("headers", []),
        "rows": data.get("rows", []),
    }


def _embed_cleaned_images(
    html: str,
    cleaned_images: list[tuple[bytes, str, str]],
    card_used: bool,
) -> str:
    """把去水印后的图片嵌入正文末尾；若已全部转成卡片则不再重复贴图。"""
    if not cleaned_images or card_used:
        return html
    blocks = ['<section style="margin:18px 0;">']
    blocks.append('<p style="color:#164b86;font-weight:600;font-size:14px;margin:6px 0;">'
                  '📎 原文图表（已去除原水印）</p>')
    for data, mime, _url in cleaned_images:
        b64 = base64.b64encode(data).decode()
        src = f"data:{mime or 'image/jpeg'};base64,{b64}"
        blocks.append(
            f'<img src="{src}" style="max-width:100%;border-radius:8px;'
            f'margin:8px 0;box-shadow:0 2px 10px rgba(0,0,0,.08);">'
        )
    blocks.append("</section>")
    return html + "\n" + "\n".join(blocks)


# ── 7.6 图片表格检测 + 视觉卡片包装（无视觉模型时的兜底）──────────────


def _looks_like_table_image(img_bytes: bytes) -> bool:
    """通过图片尺寸、宽高比和文件大小严格判断是否为数据表格图片。

    排除：横幅/封面（太宽太矮）、小图标、logo、装饰图。
    数据表格特征：
      - 面积 >= 200,000 px²（至少 ~450x450）
      - 高度 >= 500px（表格需要纵向空间容纳多行）
      - 文件大小 >= 20KB（真实表格含文字/线条，不会太小）
      - 宽高比 0.35 ~ 2.5（排除超宽横幅和超窄竖条）
    """
    try:
        import cv2
        import numpy as np
        # 快速检查文件大小（无需解码即可过滤小图）
        if len(img_bytes) < 20000:
            return False
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False
        h, w = img.shape[:2]
        area = w * h
        ratio = w / max(h, 1)
        # 严格条件：大图 + 足够高 + 合理比例
        return (
            area >= 200_000       # 至少 ~450x450
            and h >= 500           # 表格需要纵向行数
            and 0.35 <= ratio <= 2.5  # 排除横幅(>2.5)和竖条(<0.35)
        )
    except Exception:
        return False


def _pick_best_table_image(
    table_images: list[tuple[bytes, str, str]],
) -> tuple[bytes, str, str] | None:
    """从候选表格图片中选出最可能包含数据的那张。

    策略：按像素面积降序排列，取最大的。
    真实数据表格通常比封面/装饰图大得多。
    """
    if not table_images:
        return None
    import cv2
    import numpy as np

    scored = []
    for img_bytes, mime, url in table_images:
        try:
            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            h, w = img.shape[:2]
            # 综合评分：面积权重最高，其次高度（表格需要纵向空间），再次文件大小
            score = (w * h) * 1.0 + h * 100 + len(img_bytes) * 0.01
            scored.append((score, img_bytes, mime, url))
        except Exception:
            continue

    if not scored:
        return table_images[0]  # 兜底：返回第一张

    scored.sort(key=lambda x: x[0], reverse=True)
    _, best_bytes, best_mime, best_url = scored[0]
    return (best_bytes, best_mime, best_url)


def _build_visual_card_wrapper(
    core: ExtractedCore,
    table_img: tuple[bytes, str, str],
) -> dict:
    """把无法 OCR 的表格图片包装进凭他教育知识卡片的视觉框架。

    返回 card_fields 格式，让 _generate_knowledge_card 生成含图的卡片 HTML。
    卡片结构：标题(来自文章) + 副标题 + 统计栏(图片数量) +
              表格区域(嵌入清理后的原图) + 品牌页脚。
    """
    img_bytes, mime, _url = table_img
    b64 = base64.b64encode(img_bytes).decode()
    img_src = f"data:{mime or 'image/jpeg'};base64,{b64}"

    # 标题来自文章
    title = (core.original_title or "数据一览").split("｜")[0].split("|")[0].strip()
    title = title[:18] if title else "数据一览"
    subtitle = "数据明细"

    # 用一张特殊行标记"这是图片表格"——_generate_knowledge_card 检测到后用 <img> 替代 <table>
    rows = [["__IMAGE_TABLE__:" + img_src]]
    headers = ["数据图表"]

    return {
        "title": title,
        "subtitle": subtitle,
        "stats": [
            {"label": "数据来源", "value": core.source_account or "公开渠道", "unit": ""},
            {"label": "整理方", "value": "凭他教育", "unit": ""},
        ],
        "table_title": "原文数据（已去除原水印）",
        "headers": headers,
        "rows": rows,
        "_is_visual_wrapper": True,  # 标记：让渲染函数走图片路径
    }


# ── 8. 导出：Word / 微信公众号 HTML ────────────────────────────────────────


def _b64_img_src(img: ArticleImage) -> str:
    """返回图片的 data URI（优先用已加水印的处理后字节）。"""
    if img.processed_data:
        b64 = base64.b64encode(img.processed_data).decode()
        return f"data:{img.processed_mime or 'image/png'};base64,{b64}"
    return img.url


def _parse_table_html(html: str) -> tuple[list[str], list[list[str]]]:
    """从 <table> HTML 中解析出表头与数据行（轻量正则，无需 bs4）。"""
    def _cells(row_html: str) -> list[str]:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL | re.IGNORECASE)
        out = []
        for c in cells:
            c = re.sub(r"<[^>]+>", "", c)          # 去标签
            c = re.sub(r"&[a-z]+;", "", c)          # 去实体
            out.append(c.strip())
        return out

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
    if not rows:
        return [], []
    matrix = [_cells(r) for r in rows]
    headers = matrix[0] if matrix else []
    body = matrix[1:] if len(matrix) > 1 else []
    return headers, body


def _add_runs_with_caution(paragraph, text: str) -> None:
    """把文本写入段落，并将 [[CAUTION:...]] 标记渲染为「加粗+下划线」原生 run。

    这样生成的 Word 中，待复核内容是可单独选中的格式（非图片/域），
    用户下载后可在本地 Word 直接取消下划线/加粗。
    """
    from docx.shared import RGBColor

    last = 0
    for m in _CAUTION_RE.finditer(text):
        if m.start() > last:
            paragraph.add_run(text[last : m.start()])
        r = paragraph.add_run(m.group(1))
        r.bold = True
        r.underline = True
        r.font.color.rgb = RGBColor(0x9A, 0x2B, 0x2B)
        last = m.end()
    if last < len(text):
        paragraph.add_run(text[last:])


def export_docx(article: TransformedArticle) -> bytes:
    """把转化后的凭他教育风格文章导出为 Word(.docx)。

    - 标题 → 一级标题；**小节标题** → 二级标题
    - 正文按段落/列表/要点渲染；图片（已加水印）内嵌
    - 表格（已加水印）转为 Word 表格；底部品牌尾注
    """
    from io import BytesIO

    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    doc = Document()

    # 默认正文字体（中文用宋体，西文用 Calibri）
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    # 标题
    h = doc.add_heading(level=0)
    run = h.add_run(article.title)
    run.font.name = "黑体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x1A, 0x3D, 0x6D)

    blocks = [b for b in article.body_text.split("\n\n") if b and b.strip()]

    image_inserted = False
    for block in blocks:
        raw = block.strip()
        # 品牌尾注（关注【凭他教育】… + 服务推广）：精确匹配口号前缀，避免与正文
        # 中含"凭他教育…关注"的段落（如结尾述评）误判
        if raw.startswith(f"关注【{BRAND_NAME}】") or (BRAND_NAME in raw and BRAND_SLOGAN in raw):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(f"关注【{BRAND_NAME}】{BRAND_SLOGAN}")
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0x1A, 0x3D, 0x6D)
            pPr = p._p.get_or_add_pPr()
            pBdr = pPr.makeelement(qn("w:pBdr"), {})
            top = pBdr.makeelement(qn("w:top"), {
                qn("w:val"): "single", qn("w:sz"): "6",
                qn("w:space"): "6", qn("w:color"): "E8E2D5",
            })
            pBdr.append(top)
            pPr.append(pBdr)
            # 服务推广文案（与口号同块，换行续写）
            p2 = doc.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r2 = p2.add_run(BRAND_PROMO)
            r2.font.size = Pt(9)
            r2.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
            continue

        # 小标题 **xxx**
        m = re.fullmatch(r"\*\*(.+?)\*\*", raw)
        if m:
            hp = doc.add_heading(level=2)
            hr = hp.add_run(m.group(1))
            hr.font.name = "黑体"
            hr._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
            hr.font.size = Pt(13)
            hr.font.color.rgb = RGBColor(0x1A, 0x3D, 0x6D)
            continue

        # 斜体出处说明 *xxx*
        if raw.startswith("*") and raw.endswith("*"):
            p = doc.add_paragraph()
            r = p.add_run(raw[1:-1])
            r.italic = True
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0x6F, 0x77, 0x82)
            continue

        # 有序列表 1. / 2.
        if re.search(r"(?m)^\d+\.\s", raw):
            for line in raw.split("\n"):
                line = line.strip()
                mm = re.match(r"^(\d+)\.\s+(.*)$", line)
                if mm:
                    p = doc.add_paragraph(style="List Number")
                    _add_runs_with_caution(p, mm.group(2))
            continue

        # 无序列表 · xxx
        if "· " in raw:
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("· "):
                    p = doc.add_paragraph(style="List Bullet")
                    _add_runs_with_caution(p, line[2:].strip("；;。 "))
            continue

        # 普通段落
        p = doc.add_paragraph()
        _add_runs_with_caution(p, raw)

    # 配图（已加水印）
    valid_imgs = [i for i in article.images if i.processed_data]
    if valid_imgs:
        if not image_inserted:
            hp = doc.add_heading(level=2)
            hr = hp.add_run("文中配图")
            hr.font.name = "黑体"
            hr._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        for img in valid_imgs:
            try:
                doc.add_picture(BytesIO(img.processed_data), width=Pt(340))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                logger.warning("Word 内嵌图片失败: %s", e)

    # 表格（已加水印）
    for t in article.tables:
        headers, body = _parse_table_html(t.html)
        if not headers and not body:
            continue
        cols = max([len(headers)] + [len(r) for r in body]) or 1
        table = doc.add_table(rows=1, cols=cols)
        table.style = "Light Grid Accent 1"
        for c, text in enumerate(headers[:cols]):
            cell = table.rows[0].cells[c]
            cell.text = text
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True
        for row in body:
            cells = table.add_row().cells
            for c in range(cols):
                cells[c].text = (row[c] if c < len(row) else "")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_wechat_html(article: TransformedArticle) -> str:
    """导出为「微信公众号格式」的完整 HTML 文档。

    可直接在浏览器打开预览，或整体复制粘贴进公众号编辑器。
    - 正文沿用内联样式的 body_html（标题/段落已按公众号排版）
    - 水印处理后的图片以 data URI 内嵌
    - 表格（已加水印）原样保留
    - 底部品牌尾注
    """
    # 去掉 body_html 末尾已有的品牌尾注 div，避免重复（导出时统一重排）
    inner = article.body_html or ""
    inner = re.sub(
        r'<div class="pingta-brand-footer">.*?</div>\s*$',
        "",
        inner,
        flags=re.DOTALL,
    ).strip()
    footer_html = _brand_footer_html()

    # 配图（水印后）
    for img in article.images:
        if not img.processed_data:
            continue
        src = _b64_img_src(img)
        inner += (
            f'<p style="text-align:center;margin:18px 0;">'
            f'<img src="{src}" style="max-width:100%;border-radius:4px;"/>'
            f"</p>"
        )

    # 表格（水印后）
    for t in article.tables:
        inner += t.html

    # 来源标注
    src_note = (
        f'<p style="font-size:13px;color:#888;margin:0 0 18px;">'
        f"来源：{article.source_account or '公开渠道'} · 由凭他教育整理改写</p>"
        if article.source_account
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{article.title}</title>
<style>
  body {{ background:#f2f2f2; margin:0; padding:24px 0;
         font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif; }}
  .wx-article {{ max-width:680px; margin:0 auto; background:#fff; padding:36px 28px;
         box-shadow:0 1px 4px rgba(0,0,0,.08); }}
  .wx-title {{ font-size:22px; font-weight:700; color:#1a1a1a; line-height:1.4; margin:0 0 6px; }}
  .wx-meta {{ font-size:13px; color:#888; margin:0 0 22px; }}
  .wx-footer {{ text-align:center; color:#8a8a8a; font-size:13px; margin-top:28px;
         padding-top:14px; border-top:1px solid #e8e2d5; }}
</style>
</head>
<body>
  <div class="wx-article">
    <h1 class="wx-title">{article.title}</h1>
    {src_note}
    {inner}
    {footer_html}
  </div>
</body>
</html>"""

