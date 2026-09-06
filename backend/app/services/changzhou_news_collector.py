"""常州本地教育实时资讯采集器。

设计约束（沿用项目铁律）：
- 只采集**公开页面**：官方公开通知/政策列表、已验证的微信公众号检索 skill、本地媒体公开列表页。
- **不登录、不绕验证码、不强爬**；遵守 robots，单源限速，失败静默跳过（不崩溃）。
- 真实外网抓取只能在用户配了网络的环境运行；本沙箱出网被封，仅验证解析/去重/分类逻辑。

采集流程：
  run_collection(settings)
    → 并发跑各适配器（教育局官网 / 微信公众号 / 本地媒体）
    → 跨源去重（URL 归一 + 标题 hash）
    → 分类（政策文件/校园公告/招生录取/学区划片/考试测评/学科竞赛/校园开放日/升学规划/媒体报道）
    → 返回 RawNewsItem 列表（入库与重要性判定交给 service 层）
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 20.0
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 域名 → 友好来源名（fallback 用 netloc）
SOURCE_NAMES: dict[str, str] = {
    "jyj.changzhou.gov.cn": "常州市教育局",
    "www.cz001.com.cn": "中吴网",
    "cz.bendibao.com": "常州本地宝",
    "www.hualongxiang.com": "化龙巷",
    "changzhou.bendibao.com": "常州本地宝",
}


@dataclass(slots=True)
class RawNewsItem:
    title: str
    url: str
    source_name: str
    summary: str
    published_at: datetime | None
    kind: str  # "official" | "media" | "wechat"
    category: str = ""  # 采集后由 classify_category 填充


# ── 工具函数 ────────────────────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    """归一化 URL 用于去重：去 fragment、去末尾斜杠、host 转小写。"""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip()
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{host}{path}{('?' + parsed.query) if parsed.query else ''}"


def canonical_news_title_key(title: str) -> str:
    """生成较稳定的标题指纹，避免同一资讯因列表噪声重复出现。"""
    normalized = title.strip().lower()
    normalized = re.sub(r"[\s　]+", "", normalized)
    normalized = re.sub(r"^[·•\-—_【\[\(（]+", "", normalized)
    normalized = re.sub(r"(?:更多|详情|全文|点击查看)$", "", normalized)
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])[0-9]$", "", normalized)
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized)
    return normalized


_DATE_PATTERNS = [
    (re.compile(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})"), "%Y%m%d"),
    (re.compile(r"(\d{1,2})[-/月.](\d{1,2})日?"), "%m%d"),
]


def extract_date(text: str) -> datetime | None:
    """从一段文本里尽量解析出日期。"""
    if not text:
        return None
    for pattern, _ in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if len(m.groups()) == 3:
                y, mo, d = (int(x) for x in m.groups())
                return datetime(y, mo, d, tzinfo=UTC)
            if len(m.groups()) == 2:
                mo, d = (int(x) for x in m.groups())
                # 只有月日，默认当年
                now = datetime.now(UTC)
                return datetime(now.year, mo, d, tzinfo=UTC)
        except ValueError:
            continue
    return None


# 分类优先级：先匹配具体学段，再退回通用政策/招生/考试类。
_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("小升初", ("小升初",)),
    (
        "初升高",
        (
            "初升高", "中考", "中招", "升高中", "指标生",
            "中考成绩", "中考分数线", "中考录取", "普高",
        ),
    ),
    ("高考", ("高考", "高三", "普通高考", "高考成绩", "高考分数线", "高考录取", "高考志愿")),
    ("政策文件", ("政策", "文件", "办法", "规定", "实施意见", "细则", "条例")),
    ("校园公告", ("通知", "公告", "通报", "公示")),
    ("招生录取", ("招生", "录取", "报名", "志愿填报", "入学")),
    ("学区划片", ("学区", "划片", "对口", "施教区")),
    ("考试测评", ("考试", "统考", "模考", "调研", "学业质量")),
    ("学科竞赛", ("竞赛", "比赛", "奥赛", "白名单")),
    ("校园开放日", ("开放日", "校园开放", "探校")),
    (
        "升学规划",
        (
            "升学", "考研", "留学", "转学", "幼升小", "国际学校", "升学规划",
            "综评", "强基计划", "中外合作办学", "港澳升学", "保送",
        ),
    ),
]


def classify_category(text: str) -> str:
    """根据标题+摘要关键词归到固定分类；命中不到归为「媒体」。"""
    for category, keywords in _CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "媒体"


# 升学规划业务相关性：服务「常州高考 + 全国高校招生 + 综评/强基/中外合办」。
GAOKAO_FOCUS_KEYWORDS = (
    "高考", "高三", "普通高考", "新高考", "志愿", "志愿填报", "本科", "专科",
    "高校", "大学", "院校", "专业", "招生", "录取", "分数线", "投档线", "位次",
    "一分一段", "提前批", "强基", "强基计划", "综合评价", "综评", "选科",
    "首选科目", "再选科目", "学业水平", "合格考", "等级考", "一模", "二模",
    "三模", "保送", "艺考", "体育单招", "港澳升学", "中外合作办学",
    "高中升学", "升学规划",
)

ADMISSION_PLANNING_KEYWORDS = (
    "招生简章", "本科招生", "普通本科招生", "高校招生", "大学招生", "院校招生",
    "招生章程", "招生计划", "招生专业", "选科要求", "专业组", "院校专业组",
    "综合评价招生", "综合评价录取", "强基计划招生", "强基计划报名",
    "中外合作", "中外合作办学", "国际本科", "港澳高校", "香港高校",
    "澳门高校", "内地招生", "专项计划", "高校专项", "地方专项", "国家专项",
    "保送生", "少年班", "丘成桐", "拔尖计划", "双一流", "985", "211",
)

GAOKAO_CONTEXT_KEYWORDS = (
    "高中", "普通高中", "江苏省", "常州", "全国", "考生", "家长", "报名",
    "考试", "政策", "办法", "通知", "公告", "公示",
)

LOW_SIGNAL_EDUCATION_KEYWORDS = (
    "教育", "学校", "学生", "教师", "校长", "课堂", "教研", "培训", "会议",
)

NOISE_KEYWORDS = (
    "食堂", "供餐", "安保", "反恐", "消防", "安全演练", "培训会", "工作培训",
    "党建", "工会", "慰问", "招聘", "采购", "招标", "课后服务", "双减",
    "幼儿园", "幼升小", "小升初", "中考", "中招", "职教高考", "中职", "职高",
    "考研", "留学",
)


def is_education_related(text: str) -> bool:
    """判断一条资讯是否与教育相关（用于过滤泛本地新闻）。"""
    return is_gaokao_admission_related(text)


def gaokao_relevance_score(text: str) -> int:
    """升学规划业务相关性评分，用于采集过滤和排序。

    强信号来自高考志愿、全国高校招生、强基综评、中外合办等；普通校园动态会被降权。
    """
    score = 0
    score += sum(12 for keyword in GAOKAO_FOCUS_KEYWORDS if keyword in text)
    score += sum(18 for keyword in ADMISSION_PLANNING_KEYWORDS if keyword in text)
    score += sum(3 for keyword in GAOKAO_CONTEXT_KEYWORDS if keyword in text)
    score += sum(1 for keyword in LOW_SIGNAL_EDUCATION_KEYWORDS if keyword in text)
    score -= sum(18 for keyword in NOISE_KEYWORDS if keyword in text)
    return score


def is_gaokao_admission_related(text: str) -> bool:
    """只保留升学规划业务相关内容，过滤泛教育碎片信息。"""
    if any(keyword in text for keyword in NOISE_KEYWORDS) and not any(
        keyword in text
        for keyword in (
            "高考", "志愿", "录取", "本科", "专科", "强基", "综评", "综合评价",
            "中外合作", "招生简章", "高校招生", "大学招生", "港澳高校",
        )
    ):
        return False
    return gaokao_relevance_score(text) >= 12


# 新鲜度闸门：能解析出日期且超过该天数的旧闻直接剔除（默认 90 天）。
MAX_AGE_DAYS = 90


def _source_name_for(netloc: str) -> str:
    host = netloc.lower()
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host


def _is_gov(netloc: str) -> bool:
    return netloc.endswith(".gov.cn") or netloc.endswith(".gov")


# ── 适配器基类 ──────────────────────────────────────────────────────────────


class BaseNewsAdapter:
    async def collect(self, settings: Settings) -> list[RawNewsItem]:  # pragma: no cover - 接口
        raise NotImplementedError


class _HttpListAdapter(BaseNewsAdapter):
    """通用公开列表页适配器：抓取页面里看起来像"文章"的链接。"""

    def __init__(self, urls: list[str], kind: str, same_site_only: bool) -> None:
        self._urls = urls
        self._kind = kind
        self._same_site_only = same_site_only

    async def collect(self, settings: Settings) -> list[RawNewsItem]:
        items: list[RawNewsItem] = []
        limit = settings.changzhou_news_per_source_limit
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
        ) as client:
            for page_url in self._urls:
                try:
                    resp = await client.get(page_url)
                except Exception as exc:  # noqa: BLE001 - 单源失败不拖垮整体
                    logger.warning("采集源失败 %s: %s", page_url, exc)
                    continue
                if resp.status_code >= 400:
                    logger.warning("采集源 HTTP %s: %s", resp.status_code, page_url)
                    continue
                items.extend(self._parse(resp.text, page_url, limit))
        return items

    def _parse(self, html: str, page_url: str, limit: int) -> list[RawNewsItem]:
        soup = BeautifulSoup(html, "html.parser")
        base_netloc = urlparse(page_url).netloc.lower()
        found: list[RawNewsItem] = []
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            href = (a.get("href") or "").strip()
            if not text or not (6 <= len(text) <= 60):
                continue
            if not href or href.startswith(("javascript:", "#", "mailto:", "tel:")):
                continue
            abs_url = urljoin(page_url, href)
            parsed = urlparse(abs_url)
            host = parsed.netloc.lower()
            if not host:
                continue
            if (
                self._same_site_only
                and host != base_netloc
                and not host.endswith("." + base_netloc)
            ):
                continue
            if not self._same_site_only and not _is_gov(host) and host != base_netloc:
                continue
            # 跳过纯导航/栏目名
            if text in ("首页", "更多", "详情", "查看", "more", "首页", "网站地图"):
                continue
            parent = a.find_parent("li") or a.parent
            block_text = parent.get_text(" ", strip=True) if parent else text
            published_at = extract_date(block_text)
            summary = block_text.replace(text, "").strip()
            if len(summary) > 120:
                summary = summary[:120] + "…"
            # 本地/官网是混合资讯页，只保留标题明确指向高考升学的内容。
            if not is_gaokao_admission_related(f"{text} {summary}"):
                continue
            found.append(
                RawNewsItem(
                    title=text,
                    url=abs_url,
                    source_name=_source_name_for(host),
                    summary=summary,
                    published_at=published_at,
                    kind=self._kind,
                )
            )
            if len(found) >= limit:
                break
        return found


class GovNoticeAdapter(_HttpListAdapter):
    """教育局等官方公开通知页（跨子域的 gov.cn 都算官方）。"""

    def __init__(self, urls: list[str]) -> None:
        super().__init__(urls, kind="official", same_site_only=False)


class LocalMediaAdapter(_HttpListAdapter):
    """本地媒体公开列表页（同站内的链接）。"""

    def __init__(self, urls: list[str]) -> None:
        super().__init__(urls, kind="media", same_site_only=True)


class WechatAdapter(BaseNewsAdapter):
    """复用已验证的 wechat-article-search skill，按检索词搜近期常州教育文章。"""

    def __init__(self, queries: list[str]) -> None:
        self._queries = queries

    async def collect(self, settings: Settings) -> list[RawNewsItem]:
        from app.services.wechat_transform_service import search_account_articles

        items: list[RawNewsItem] = []
        limit = max(3, settings.changzhou_news_per_source_limit // 2)
        for query in self._queries:
            try:
                refs = await search_account_articles(query, limit=limit, timeout=20.0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("微信检索失败 %s: %s", query, exc)
                continue
            for ref in refs:
                if not ref.url or not ref.title:
                    continue
                published_at = None
                if ref.published_at:
                    published_at = extract_date(ref.published_at)
                if not is_gaokao_admission_related(f"{ref.title} {ref.summary}"):
                    continue
                items.append(
                    RawNewsItem(
                        title=ref.title,
                        url=ref.url,
                        source_name=ref.account_name or "微信公众号",
                        summary=(ref.summary or "")[:120],
                        published_at=published_at,
                        kind="wechat",
                    )
                )
        return items


# ── 去重 + 分类 + 组装 ───────────────────────────────────────────────────────


def _dedupe(items: list[RawNewsItem]) -> list[RawNewsItem]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[RawNewsItem] = []
    for item in items:
        key_url = normalize_url(item.url) if item.url else ""
        key_title = canonical_news_title_key(item.title)
        if key_url and key_url in seen_urls:
            continue
        if key_title and key_title in seen_titles:
            continue
        if key_url:
            seen_urls.add(key_url)
        if key_title:
            seen_titles.add(key_title)
        out.append(item)
    return out


async def run_collection(settings: Settings) -> list[RawNewsItem]:
    """并发跑所有启用的适配器，去重并分类，返回待入库原始条目。

    异步实现，可在 FastAPI 事件循环 / 自动采集循环内直接 await。
    """
    adapters: list[BaseNewsAdapter] = []
    if settings.changzhou_news_gov_urls:
        adapters.append(GovNoticeAdapter(settings.changzhou_news_gov_urls))
    if settings.changzhou_news_local_media_urls:
        adapters.append(LocalMediaAdapter(settings.changzhou_news_local_media_urls))
    if settings.changzhou_news_wechat_queries:
        adapters.append(WechatAdapter(settings.changzhou_news_wechat_queries))
    if not adapters:
        return []

    results = await asyncio.gather(
        *(adapter.collect(settings) for adapter in adapters),
        return_exceptions=True,
    )
    merged: list[RawNewsItem] = []
    for res in results:
        if isinstance(res, Exception):
            logger.warning("适配器异常: %s", res)
            continue
        merged.extend(res)
    for item in merged:
        if not item.category:
            item.category = classify_category(f"{item.title} {item.summary}")
    merged = [
        item
        for item in merged
        if is_gaokao_admission_related(f"{item.title} {item.summary} {item.category}")
    ]
    # 新鲜度闸门：能解析出日期且超过 MAX_AGE_DAYS 的旧闻剔除（无法解析日期的保留，避免误删）。
    now = datetime.now(UTC)
    merged = [
        item
        for item in merged
        if item.published_at is None or (now - item.published_at).days <= MAX_AGE_DAYS
    ]
    merged = _dedupe(merged)
    merged.sort(
        key=lambda x: (
            gaokao_relevance_score(f"{x.title} {x.summary} {x.category}"),
            x.published_at is not None,
            x.published_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return merged


class ChangzhouNewsAutoCollector:
    """后台定时采集循环（镜像 SocialVideoAutoCollector）。"""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings,
        interval_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="changzhou-news-auto-collector")
        logger.info(
            "changzhou_news_auto_collector_started",
            extra={"interval": self._interval_seconds},
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        logger.info("changzhou_news_auto_collector_stopped")

    async def collect_once(self) -> int:
        from app.repositories.sqlalchemy_changzhou_news_repository import (
            SQLAlchemyChangzhouNewsRepository,
        )
        from app.services.changzhou_news_service import ChangzhouNewsService

        async with self._session_factory() as session:
            service = ChangzhouNewsService(SQLAlchemyChangzhouNewsRepository(session))
            result = await service.collect_news(self._settings)
            await session.commit()
            return result.created

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                created = await self.collect_once()
                logger.info(
                    "changzhou_news_auto_collect_finished",
                    extra={"created_count": created},
                )
            except Exception:  # noqa: BLE001
                logger.exception("changzhou_news_auto_collect_failed")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                continue
