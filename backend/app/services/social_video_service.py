import re
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.config import Settings
from app.domain.social_creator import SocialCreator, SocialCreatorCategory
from app.domain.social_video import SocialVideo, SocialVideoPlatform, SocialVideoScope
from app.repositories.social_creator_repository import SocialCreatorRepository
from app.repositories.social_video_repository import SocialVideoRepository
from app.services.hot_threshold_store import get_threshold
from app.services.llm_client import call_llm
from app.services.social_creator_service import normalize_keywords
from app.services.social_video_transcript_provider import (
    DisabledSocialVideoTranscriptProvider,
    LocalFileTranscriptProvider,
    SocialVideoTranscriptProvider,
)
from app.services.verified_video_provider import (
    DISCOVERY_QUERIES,
    DisabledVerifiedVideoProvider,
    VerifiedVideo,
    VerifiedVideoProvider,
)


@dataclass(frozen=True, slots=True)
class SocialVideoCollectionLog:
    id: int
    started_at: datetime
    finished_at: datetime
    discovered: int
    hot_matched: int
    scope_rejected: int
    duplicate_skipped: int
    created: int
    status: str
    message: str


def _threshold_label(platform: SocialVideoPlatform, scope: SocialVideoScope) -> str:
    if scope == SocialVideoScope.CHANGZHOU_LOCAL and platform == SocialVideoPlatform.DOUYIN:
        return "常州范围抖音"
    if scope == SocialVideoScope.CHANGZHOU_LOCAL:
        return "常州范围微信视频号"
    if platform == SocialVideoPlatform.DOUYIN:
        return "抖音大博主"
    return "微信视频号大博主"


def threshold_for(platform: SocialVideoPlatform, scope: SocialVideoScope) -> tuple[int, int, str]:
    like_threshold, save_threshold = get_threshold(platform.value, scope.value)
    label = _threshold_label(platform, scope)
    return like_threshold, save_threshold, f"{label}：{like_threshold}赞或{save_threshold}收藏"


def evaluate_hot_video(
    *,
    platform: SocialVideoPlatform,
    scope: SocialVideoScope,
    likes: int,
    saves: int,
) -> tuple[bool, str, str]:
    like_threshold, save_threshold, threshold = threshold_for(platform, scope)
    is_hot = likes >= like_threshold or saves >= save_threshold
    if is_hot:
        reason = f"已命中推送阈值：{likes}赞、{saves}收藏，规则为{threshold}。"
    else:
        reason = f"暂未达标：{likes}赞、{saves}收藏，规则为{threshold}。"
    return is_hot, threshold, reason


def matches_topic(*, title: str, creator: str, keywords: list[str]) -> bool:
    text = f"{title} {creator}"
    return any(keyword.strip() and keyword.strip() in text for keyword in keywords)


DISCOVERY_KEYWORDS = [
    "高考",
    "升学",
    "志愿填报",
    "专业选择",
    "强基计划",
    "综评",
    "选科",
    "录取",
    "规划",
]
DISCOVERY_EXCLUDED_KEYWORDS = ["中考", "中职", "职高", "小升初", "幼升小", "留学", "考研", "专升本"]
DOUYIN_ID_PATTERN = re.compile(r"/(?:share/)?(?:video|note)/(\d+)")
FILLER_PATTERN = re.compile(
    r"(大家好|嗯+哼?|呃+|啊+|呀+|哎+|唉+|额+|哦+|噢+|喔+|哈+|嘛+|"
    r"呐+|嗨+|呢+|呗+|哟+|咦+|咳+|这个|那个|这些|那些|就是说|"
    r"就是|然后|其实|那么|所以说|你知道|你知道吧|对吧|是不是|对不对|"
    r"怎么说呢|咱们|我跟你讲|我跟你说|说白了|也就是说|换句话说|"
    r"简单来说|总的来说|等一下|稍等|那个啥|这个嘛|的话)"
)
_collection_logs: deque[SocialVideoCollectionLog] = deque(maxlen=20)
_collection_log_id = 0


def matches_gaokao_discovery_scope(*, title: str, creator: str) -> bool:
    text = f"{title} {creator}"
    if any(keyword in text for keyword in DISCOVERY_EXCLUDED_KEYWORDS):
        return False
    return any(keyword in text for keyword in DISCOVERY_KEYWORDS)


def canonical_social_video_url_key(url: str) -> str:
    match = DOUYIN_ID_PATTERN.search(url)
    if match:
        return f"douyin:{match.group(1)}"
    return url.split("?", maxsplit=1)[0].rstrip("/")


def _is_garbage_transcript(text: str) -> bool:
    """检测 Whisper/字幕 输出是否为无效垃圾内容。

    拦截场景：
    - 清洗后过短（< 15 字符）
    - 无中文字符（纯英文乱码如 "by bwd6"）
    - 仅含话题标签/创作者水印
    """
    t = text.strip()
    if len(t) < 15:
        return True
    # 必须包含至少一个汉字
    chinese_chars = sum(1 for c in t if "\u4e00" <= c <= "\u9fff")
    if chinese_chars < 3:
        return True
    return False


# 强歌词信号：命中任意一个即判定为音乐/歌词内容
_LYRICS_MARKERS = (
    "原唱", "歌词", "伴奏", "编曲", "作曲", "作词", "演唱", "翻唱",
    "钢琴版", "吉他版", "小提琴版", "纯音乐", " instrumental",
)
_EDU_TRANSCRIPT_KEYWORDS = (
    "高考", "志愿", "填报", "专业", "院校", "大学", "本科", "专科", "录取",
    "分数", "位次", "投档", "招生", "选科", "强基", "综评", "考生", "家长",
    "就业", "保研", "学科", "学校", "批次", "提前批", "滑档", "退档",
)
_LYRIC_STYLE_WORDS = (
    "爱", "心", "梦", "远方", "星光", "月光", "花开", "孤独", "眼泪",
    "思念", "拥抱", "天空", "风雨", "青春", "离开", "回来", "等待",
)


def _classify_content(transcript: str, title: str = "") -> tuple[str, str]:
    """对清洗后的转写稿做内容分类。

    返回 (类别, 说明)：
    - "lyrics"   ：疑似音乐/歌词，不应作为知识性文稿
    - "title_only"：疑似仅为视频标题/话题标签，无实质语音信息
    - "valid"    ：正常可复用内容
    """
    t = transcript.strip()
    # 1) 歌词强信号
    if any(m.lower() in t.lower() for m in _LYRICS_MARKERS):
        return "lyrics", "疑似音乐/歌词内容（检测到原唱/作词/伴奏等标记），歌词不属于知识性语音内容"
    if not _has_education_signal(t) and _looks_like_lyrics(t):
        return "lyrics", "疑似识别到背景音乐歌词，未检测到高考升学讲解关键词"
    # 2) 标题式：去掉话题标签后高度匹配视频标题，或整体极短
    stripped = re.sub(r"#[\w一-鿿]+|#", " ", t)
    stripped = re.sub(r"\s+", "", stripped)
    title_core = re.sub(r"#[\w一-鿿]+|#|\s+", "", title or "")
    if stripped and title_core and stripped == title_core[: len(stripped)] and len(stripped) < 30:
        return "title_only", "内容疑似仅为视频标题/话题标签，无实质性语音信息"
    if len(stripped) < 15:
        return "title_only", "内容过短，疑似仅为标题/话题标签，无实质性语音信息"
    # 3) 高重复率（歌词或无效口播）：句子级去重后重复占比过高
    sentences = [s for s in re.split(r"[。！？!?\n]+", t) if len(s.strip()) >= 5]
    if len(sentences) >= 4:
        unique = set(sentences)
        dup_ratio = 1 - len(unique) / len(sentences)
        if dup_ratio >= 0.4:
            return "lyrics", "检测到大量重复句式，疑似音乐歌词或无效口播，不适合作为知识文稿"
    return "valid", ""


def _has_education_signal(text: str) -> bool:
    return any(keyword in text for keyword in _EDU_TRANSCRIPT_KEYWORDS)


def _looks_like_lyrics(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return False
    lyric_hits = sum(1 for word in _LYRIC_STYLE_WORDS if word in compact)
    sentences = [s.strip() for s in re.split(r"[。！？!?\n,，]+", text) if len(s.strip()) >= 3]
    short_sentence_ratio = 0.0
    if sentences:
        short_sentence_ratio = (
            sum(1 for sentence in sentences if len(sentence) <= 12) / len(sentences)
        )
    return lyric_hits >= 3 or (len(sentences) >= 4 and short_sentence_ratio >= 0.65)


def clean_video_transcript_text(text: str) -> str:
    normalized = re.sub(r"#[\w一-鿿]+", " ", text)  # 去掉话题标签
    normalized = normalized.replace("#", " ")
    normalized = re.sub(r"([嗯啊呃额哦噢喔哈哎唉呀嘛呢呐呗哟咦咳])\1+", r"\1", normalized)
    normalized = (
        normalized.replace("。", "\n")
        .replace("！", "\n")
        .replace("？", "\n")
        .replace("；", "\n")
    )
    normalized = FILLER_PATTERN.sub("", normalized)
    lines = []
    for line in normalized.splitlines():
        compact = re.sub(r"\s+", " ", line).strip(" ，,；;：:　")
        if compact:
            lines.append(compact)
    return "\n".join(_dedupe_preserving_order(lines))


def _normalize_sentences(text: str) -> list[str]:
    """切分为干净句子（去空白、去首尾标点）。
    
    支持两种输入：
    1. 已有标点的文本 → 按标点切分
    2. 无标点的 Whisper 原始输出 → 按语义断点（连词/序数词/长停顿）切分
    """
    # 先尝试按中文标点切分
    raw = re.split(r"[。！？;.!?；\n]+", text)
    has_punct = any(p in text for p in "。！？.!?")
    
    out: list[str] = []
    for sentence in raw:
        compact = re.sub(r"\s+", "", sentence).strip(" ，,；;：:　、")
        if len(compact) >= 4:
            out.append(compact)
    
    # 如果切出来只有 0-1 句但原文很长，说明是无标点文本，走语义断句
    if len(out) <= 1 and len(text) > 20 and not has_punct:
        return _split_unpunctuated(text)
    
    return out


# 语义断句用的过渡标记（出现在这些词前面或后面断开）
_BREAK_BEFORE = {
    "然后", "接着", "另外", "此外", "还有", "总之", "所以", "因此",
    "最后", "比如", "例如", "再说", "接下来", "首先", "其次",
    "第一", "第二", "第三", "第四", "第五",
}
_BREAK_AFTER = {
    "的话", "以后", "之后", "的时候", "的情况下", "方面", "来说",
    "来看", "来讲", "而言", "的角度",
}


def _split_unpunctuated(text: str, max_chunk: int = 50) -> list[str]:
    """对无标点的 Whisper 原始输出做语义断句。
    
    策略：
    1. 按过渡词/连接词/序数词断开
    2. 超过 max_chunk 字的强制断句
    3. 过短碎片合并到前一句
    """
    import re as _re
    
    # 先清洗空白
    clean = _re.sub(r"\s+", "", text)
    
    # 构建正则：在断点词前后插入分隔符
    pattern = "|".join(_re.escape(w) for w in sorted(_BREAK_BEFORE, key=len, reverse=True))
    # 在断点词前切开
    parts = _re.split(f"(?={pattern})", clean)
    
    # 再按长度强制断句
    result: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        while len(part) > max_chunk:
            # 尝试在最后一个"的/了/是/和/与"处断开
            cut = max_chunk
            for delim in ["的", "了", "是", "和", "与", "，"]:
                pos = part.rfind(delim, max_chunk - 10, max_chunk + 5)
                if pos > max_chunk // 2:
                    cut = pos + 1
                    break
            result.append(part[:cut])
            part = part[cut:]
        if part:
            result.append(part)
    
    # 合并过短碎片（<6字并入前句）
    merged: list[str] = []
    for s in result:
        if merged and len(s) < 6:
            merged[-1] += s
        else:
            merged.append(s)
    
    return [s for s in merged if len(s) >= 4]


def _sentence_similarity(a: str, b: str) -> float:
    """基于字符交集的近似重复度（0~1）。"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    denom = min(len(sa), len(sb))
    return inter / denom if denom else 0.0


def _dedupe_sentences(sentences: list[str]) -> list[str]:
    """去除完全重复与高度相似（>0.8）的句子，保留首次出现。"""
    result: list[str] = []
    for s in sentences:
        if any(s == r or _sentence_similarity(s, r) > 0.8 for r in result):
            continue
        result.append(s)
    return result


def _merge_fragments(sentences: list[str], min_len: int = 12) -> list[str]:
    """把过短（< min_len）的碎片句并入前一句，避免脚本支离破碎。"""
    merged: list[str] = []
    for s in sentences:
        if merged and len(s) < min_len:
            merged[-1] = merged[-1] + s
        else:
            merged.append(s)
    return merged


def _group_into_script(
    sentences: list[str],
    max_per_paragraph: int = 2,
    max_length: int = 90,
) -> str:
    """按 1-2 分钟口播节奏分段：每段 1-2 句、约 60-90 字，段落间留气口。
    
    每句末尾恢复标点（。/？/！），段内句间用逗号衔接，
    输出为可直接阅读的专业文稿格式，而非无标点词堆。
    """
    paragraphs: list[str] = []
    buffer: list[str] = []
    length = 0
    for sentence in sentences:
        buffer.append(sentence)
        length += len(sentence)
        if len(buffer) >= max_per_paragraph or length >= max_length:
            paragraphs.append(_join_sentences(buffer))
            buffer = []
            length = 0
    if buffer:
        paragraphs.append(_join_sentences(buffer))
    return "\n\n".join(paragraphs)


def _join_sentences(sentences: list[str]) -> str:
    """将句子列表拼接为带标点的通顺段落。
    
    - 单句：末尾加「。」
    - 多句：中间用「，」连接，末尾加「。」
    - 含疑问词的句子末尾用「？」
    """
    if not sentences:
        return ""
    if len(sentences) == 1:
        return _sentence_with_punct(sentences[0])
    # 多句：中间逗号分隔，末尾句号
    parts = [_sentence_with_punct(s, terminal=False) for s in sentences]
    text = "，".join(parts)
    # 确保末尾是句号
    text = text.rstrip("，。、；：!?！？")
    return text + "。"


_SENTENCE_END_PUNCT = {"。", "！", "？", "!", "?", ";", "；"}
_QUESTION_WORDS = {"什么", "怎么", "如何", "哪", "谁", "为什么", "是否", "能否",
                   "多少", "几", "怎样", "何", "咋"}


def _sentence_with_punct(text: str, *, terminal: bool = True) -> str:
    """给句子加合适的标点。"""
    if not text:
        return text
    # 已有尾标点则保留
    if text[-1] in _SENTENCE_END_PUNCT:
        return text
    # 疑问句判断
    has_q = any(w in text for w in _QUESTION_WORDS)
    punct = "？" if (has_q and terminal) else ("。" if terminal else "")
    return text + punct


async def generate_manuscript(cleaned: str, settings: "Settings | None" = None) -> str:
    """把去语气词后的清洗稿整理成适合 1-2 分钟口播的文稿。

    规则引擎（离线可用）：去重 → 合并碎片 → 按口播节奏分段，去除重复与不连贯片段。
    若 settings.manuscript_provider 为某个大模型厂商（doubao/deepseek/qwen/zhipu/kimi）
    且配置了对应 key，则优先调用该模型润色（语义级连贯重写）；失败或返回为空时回退到规则引擎。
    本项目不依赖 OpenAI。
    """
    sentences = _normalize_sentences(cleaned)
    if not sentences:
        return ""
    if settings is not None and settings.manuscript_provider != "rule":
        polished = await _polish_manuscript_with_llm("\n".join(sentences), settings)
        if polished:
            return polished
    sentences = _dedupe_sentences(sentences)
    sentences = _merge_fragments(sentences)
    if not sentences:
        return ""
    return _group_into_script(sentences)


async def _polish_manuscript_with_llm(cleaned: str, settings: "Settings") -> str | None:
    """调用配置的大模型厂商润色文稿；未配置或失败时返回 None（回退规则引擎）。"""
    if settings.manuscript_provider in ("rule", "none", ""):
        return None
    system_prompt = (
        "你是一名专业的内容编辑。下面是一段抖音教育类视频的口语化转写（已去除语气词）：\n"
        "请将其整理成通顺、连贯的文稿：修正标点、合理分段、去除残留口语词与重复，"
        "保留原意与关键数据，不要添油加醋。直接输出文稿正文，不要使用标题，不要解释。"
    )
    return await call_llm(
        settings,
        settings.manuscript_provider,
        cleaned,
        system=system_prompt,
        temperature=0.3,
        timeout=60,
    )


def _dedupe_preserving_order(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result


def video_recommendation_score(video: SocialVideo) -> int:
    interaction_score = video.likes + video.saves * 2
    age_days = max((datetime.now(UTC) - _ensure_aware(video.published_at)).days, 0)
    freshness_bonus = max(30 - age_days, 0) * 120
    topic_bonus = (
        800
        if matches_gaokao_discovery_scope(title=video.title, creator=video.creator)
        else 0
    )
    return interaction_score + freshness_bonus + topic_bonus


def list_collection_logs() -> list[SocialVideoCollectionLog]:
    return list(_collection_logs)


def _record_collection_log(
    *,
    started_at: datetime,
    discovered: int,
    hot_matched: int,
    scope_rejected: int,
    duplicate_skipped: int,
    created: int,
) -> None:
    global _collection_log_id
    _collection_log_id += 1
    status = "已入库" if created else "无新增"
    message = (
        f"发现{discovered}条，达标{hot_matched}条，"
        f"过滤{scope_rejected}条，重复{duplicate_skipped}条，新增{created}条。"
    )
    _collection_logs.appendleft(
        SocialVideoCollectionLog(
            id=_collection_log_id,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            discovered=discovered,
            hot_matched=hot_matched,
            scope_rejected=scope_rejected,
            duplicate_skipped=duplicate_skipped,
            created=created,
            status=status,
            message=message,
        )
    )


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class VideoDiscoveryCandidate(dict[str, object]):
    pass


class VideoDiscoveryAdapter(Protocol):
    async def discover(self, keywords: list[str]) -> list[VideoDiscoveryCandidate]: ...


class PublicCatalogVideoDiscoveryAdapter:
    """Local adapter for public, manually verifiable video URLs."""

    async def discover(self, keywords: list[str]) -> list[VideoDiscoveryCandidate]:
        candidates = [
            VideoDiscoveryCandidate(
                title="填报高考志愿，遵从个人兴趣还是追逐热门专业？",
                creator="每日甘肃",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7656987460458581257",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 30, tzinfo=UTC),
            ),
            VideoDiscoveryCandidate(
                title="2026高考志愿填报指南来了！六条关键提示助你避坑",
                creator="藏视界",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7655302630884822315",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 25, tzinfo=UTC),
            ),
            VideoDiscoveryCandidate(
                title="AI时代拼的是专业还是能力？高考志愿怎么填报？",
                creator="韩秀云讲经济",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7655277710347947283",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 25, tzinfo=UTC),
            ),
            VideoDiscoveryCandidate(
                title="高考志愿填报别慌！权威专家天团坐镇山河+",
                creator="山河视频",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7655154629134683443",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 25, tzinfo=UTC),
            ),
            VideoDiscoveryCandidate(
                title="高考出分，喜忧参半！志愿填报很关键！",
                creator="学考通教育科技",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7654879155032476991",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 24, tzinfo=UTC),
            ),
            VideoDiscoveryCandidate(
                title="高考志愿填报是听孩子的还是家长？",
                creator="李嘉园博士谈升学",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7652676677864066304",
                likes=0,
                saves=0,
                published_at=datetime(2026, 6, 19, tzinfo=UTC),
            )
        ]
        return [
            candidate
            for candidate in candidates
            if matches_topic(
                title=str(candidate["title"]),
                creator=str(candidate["creator"]),
                keywords=keywords,
            )
        ]


def candidate_videos_for_creator(creator: SocialCreator) -> list[dict[str, object]]:
    """Return publicly verifiable candidate videos configured for a creator."""
    return [
        dict(item)
        for item in [
            VideoDiscoveryCandidate(
                title="高考志愿填报指导视频",
                creator="学习指导-亦木老师",
                platform=SocialVideoPlatform.DOUYIN,
                scope=SocialVideoScope.NATIONAL_INFLUENCER,
                original_url="https://jingxuan.douyin.com/m/video/7630685782566538496",
                likes=0,
                saves=0,
            )
        ]
        if item["creator"] == creator.name
        and item["platform"] == creator.platform
        and item["scope"] == creator.scope
        and matches_topic(
            title=str(item["title"]),
            creator=str(item["creator"]),
            keywords=creator.keywords,
        )
    ]


class SocialVideoService:
    def __init__(
        self,
        repository: SocialVideoRepository,
        creator_repository: SocialCreatorRepository,
        discovery_adapter: VideoDiscoveryAdapter | None = None,
        verified_video_provider: VerifiedVideoProvider | None = None,
        transcript_provider: SocialVideoTranscriptProvider | None = None,
        local_transcript_provider: LocalFileTranscriptProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._creator_repository = creator_repository
        self._discovery_adapter = discovery_adapter or PublicCatalogVideoDiscoveryAdapter()
        self._verified_video_provider = verified_video_provider or DisabledVerifiedVideoProvider()
        self._transcript_provider = (
            transcript_provider or DisabledSocialVideoTranscriptProvider()
        )
        self._local_transcript_provider = local_transcript_provider
        self._settings = settings

    async def list_videos(self) -> list[SocialVideo]:
        videos = await self._repository.list()
        return sorted(videos, key=video_recommendation_score, reverse=True)

    async def recompute_hot_flags(self) -> int:
        """按当前门槛（hot_threshold_store）重算所有视频的 is_hot/threshold/reason。

        门槛被用户修改后调用，使已采集视频立即按新标准重新判定，无需等待下次采集。
        """
        videos = await self._repository.list()
        updated = 0
        for video in videos:
            is_hot, threshold, reason = evaluate_hot_video(
                platform=video.platform,
                scope=video.scope,
                likes=video.likes,
                saves=video.saves,
            )
            if video.is_hot != is_hot or video.threshold != threshold or video.reason != reason:
                await self._repository.update_hot_flags(
                    video.id, is_hot=is_hot, threshold=threshold, reason=reason
                )
                updated += 1
        return updated

    async def create_video(
        self,
        *,
        title: str,
        creator: str,
        platform: SocialVideoPlatform,
        scope: SocialVideoScope,
        original_url: str,
        likes: int,
        saves: int,
        published_at: datetime | None = None,
        play_url: str = "",
    ) -> SocialVideo:
        now = datetime.now(UTC)
        is_hot, threshold, reason = evaluate_hot_video(
            platform=platform,
            scope=scope,
            likes=likes,
            saves=saves,
        )
        return await self._repository.create(
            SocialVideo(
                id=0,
                title=title.strip(),
                creator=creator.strip(),
                platform=platform,
                scope=scope,
                original_url=original_url.strip(),
                likes=max(likes, 0),
                saves=max(saves, 0),
                threshold=threshold,
                is_hot=is_hot,
                reason=reason,
                transcript="",
                transcript_source="",
                transcript_updated_at=None,
                manuscript="",
                published_at=published_at or now,
                collected_at=now,
                play_url=play_url.strip(),
            )
        )

    async def generate_transcript(self, video_id: int) -> SocialVideo | None:
        video = await self._repository.find_by_id(video_id)
        if video is None:
            return None
        extraction = await self._transcript_provider.extract(
            video.original_url, play_url=video.play_url or ""
        )
        if extraction is None:
            hint = (
                "（TikHub 余额不足或无法连接，且无已缓存的播放地址。"
                "充值 TikHub 或重新采集视频后可恢复转写能力）"
                if not video.play_url
                else "（无法从已缓存地址下载音频，可能链接已过期）"
            )
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=f"未提取到视频内文字{hint}",
                manuscript="",
            )
        raw_text = extraction.text
        transcript = clean_video_transcript_text(raw_text)
        if _is_garbage_transcript(transcript):
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=f"{extraction.source}（识别结果无效：内容过短或无有效语音，可能该视频无对白/纯BGM/音频异常）",
                manuscript="",
            )
        category, note = _classify_content(transcript, title=video.title)
        if category != "valid":
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=f"{extraction.source}（{note}）",
                manuscript="",
            )
        manuscript = await generate_manuscript(transcript, self._settings)
        return await self._repository.update_transcript(
            video_id,
            transcript=transcript,
            transcript_source=extraction.source,
            manuscript=manuscript,
        )

    async def generate_transcript_from_local(
        self, video_id: int, file_path: str
    ) -> SocialVideo | None:
        """方案 C：用本地媒体文件为指定视频生成转写稿 + 文稿，全程不依赖 TikHub。
        媒体文件由调用方读取后传入，转写完成即丢弃，仅把文字结果写库（不落盘、不积累）。"""
        video = await self._repository.find_by_id(video_id)
        if video is None:
            return None
        provider = self._local_transcript_provider
        if provider is None:
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=(
                    "本地文件转写未启用"
                    "（请在 .env 设置 TRANSCRIPTION_PROVIDER=local-whisper）"
                ),
                manuscript="",
            )
        extraction = await provider.extract_from_local(file_path)
        if extraction is None or not extraction.text:
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=(
                    extraction.source if extraction else "未提取到视频内文字（本地转写未启用）"
                ),
                manuscript="",
            )
        transcript = clean_video_transcript_text(extraction.text)
        if _is_garbage_transcript(transcript):
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=f"{extraction.source}（识别结果无效：内容过短或无有效语音，可能该视频无对白/纯BGM/音频异常）",
                manuscript="",
            )
        category, note = _classify_content(transcript, title=video.title)
        if category != "valid":
            return await self._repository.update_transcript(
                video_id,
                transcript="",
                transcript_source=f"{extraction.source}（{note}）",
                manuscript="",
            )
        manuscript = await generate_manuscript(transcript, self._settings)
        return await self._repository.update_transcript(
            video_id,
            transcript=transcript,
            transcript_source=extraction.source,
            manuscript=manuscript,
        )

    async def regenerate_manuscript(self, video_id: int) -> SocialVideo | None:
        video = await self._repository.find_by_id(video_id)
        if video is None:
            return None
        if not video.transcript:
            return video
        manuscript = await generate_manuscript(video.transcript, self._settings)
        return await self._repository.update_manuscript(video_id, manuscript)

    async def collect_public_videos(self) -> list[SocialVideo]:
        started_at = datetime.now(UTC)
        created: list[SocialVideo] = []
        hot_matched = 0
        scope_rejected = 0
        duplicate_skipped = 0
        seen_url_map = {
            canonical_social_video_url_key(video.original_url): video.id
            for video in await self._repository.list()
        }
        candidates = await self._verified_video_provider.discover(DISCOVERY_QUERIES)
        for video in candidates:
            if not self._is_verified_hot_video(video):
                continue
            hot_matched += 1
            # 抖音达标即推送：不再用主题硬过滤剔除中考/升学规划等内容，
            # 主题相关度仅作为推荐排序加分（见 video_recommendation_score）。
            url_key = canonical_social_video_url_key(video.original_url)
            if url_key in seen_url_map:
                await self._backfill_play_url(video, existing_id=seen_url_map[url_key])
                duplicate_skipped += 1
                continue
            seed = VideoDiscoveryCandidate(
                title=video.title,
                creator=video.creator,
                platform=video.platform,
                scope=video.scope,
                original_url=video.original_url,
                likes=video.likes,
                saves=video.saves,
                published_at=video.published_at,
                play_url=video.play_url,
            )
            creator = await self._ensure_discovered_creator(seed)
            if not creator.enabled:
                continue
            if not matches_topic(
                title=str(seed["title"]),
                creator=str(seed["creator"]),
                keywords=creator.keywords,
            ):
                continue
            existing = await self._repository.find_by_url(str(seed["original_url"]))
            if existing is not None:
                await self._backfill_play_url(video, existing=existing)
                duplicate_skipped += 1
                continue
            created.append(await self.create_video(**seed))
            seen_url_map[url_key] = created[-1].id
        _record_collection_log(
            started_at=started_at,
            discovered=len(candidates),
            hot_matched=hot_matched,
            scope_rejected=scope_rejected,
            duplicate_skipped=duplicate_skipped,
            created=len(created),
        )
        return created

    def _is_verified_hot_video(self, video: VerifiedVideo) -> bool:
        is_hot, _, _ = evaluate_hot_video(
            platform=video.platform,
            scope=video.scope,
            likes=video.likes,
            saves=video.saves,
        )
        return is_hot

    async def _backfill_play_url(
        self,
        video: VerifiedVideo,
        *,
        existing: SocialVideo | None = None,
        existing_id: int | None = None,
    ) -> None:
        """If a duplicate already exists without a play_url, backfill it so the
        local ASR can later download the audio."""
        if not video.play_url:
            return
        if existing is None and existing_id is not None:
            existing = await self._repository.find_by_id(existing_id)
        if existing is None and existing_id is None:
            existing = await self._repository.find_by_url(str(video.original_url))
        if existing is None or existing.play_url:
            return
        await self._repository.update_play_url(existing.id, play_url=video.play_url)

    async def _ensure_discovered_creator(self, seed: VideoDiscoveryCandidate) -> SocialCreator:
        creator_name = str(seed["creator"]).strip()
        existing = await self._creator_repository.find_by_name(creator_name)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        return await self._creator_repository.create(
            SocialCreator(
                id=0,
                name=creator_name,
                platform=seed["platform"],
                scope=seed["scope"],
                category=SocialCreatorCategory.GAOKAO,
                profile_url="",
                keywords=normalize_keywords(DISCOVERY_KEYWORDS),
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
