from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Education Intelligence API"
    app_version: str = "0.1.0"
    environment: str = Field(default="local", pattern="^(local|test|staging|production)$")
    debug: bool = False
    log_level: str = "INFO"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    cors_methods: list[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
    cors_headers: list[str] = ["Authorization", "Content-Type", "X-Request-ID", "X-App-Password"]
    cors_allow_credentials: bool = True
    app_access_password: str = ""

    database_url: str = "sqlite+aiosqlite:///./local.db"
    database_echo: bool = False
    database_auto_create: bool = True

    douyin_client_key: str = ""
    douyin_client_secret: str = ""
    douyin_redirect_uri: str = "http://localhost:8000/api/v1/platform-auth/douyin/callback"
    wechat_channels_app_id: str = ""
    wechat_channels_app_secret: str = ""

    social_video_auto_collect_enabled: bool = True
    social_video_auto_collect_interval_seconds: int = Field(default=600, ge=60)

    # ── 常州本地教育实时资讯采集 ────────────────────────────────────────────
    # 仅采集公开页面 / 官方公开通知 / 已验证的微信公众号检索 skill；
    # 不登录、不绕验证码、不强爬，遵守 robots 与合理限速。
    changzhou_news_auto_collect_enabled: bool = True
    changzhou_news_auto_collect_interval_seconds: int = Field(default=300, ge=60)
    # 常州市教育局等官方公开通知/政策列表页（纯公开 HTTP，无需登录）。
    # 指向"通知公告 / 政策文件"列表页即可，适配器会自动解析其中的文章链接。
    # 真实地址（2026-08-05 核实）：
    #  - https://jyj.changzhou.gov.cn/          常州市教育局官网首页（含"通知公告"+"教育新闻"板块）
    #  - https://www.changzhou.gov.cn/ns_class/zwgk_18
    #    常州市政府"政务公开>教育"信息公开列表（官方政策原文）
    changzhou_news_gov_urls: list[str] = Field(
        default_factory=lambda: [
            "https://jyj.changzhou.gov.cn/",
            "https://www.changzhou.gov.cn/ns_class/zwgk_18",
        ]
    )
    # 微信公众号检索词（复用 wechat-article-search skill，搜狗偶发限流，属软源）。
    # 每个词会检索近期相关文章，按升学规划业务相关度过滤。
    # 重点覆盖：常州高考、本科招生、综合评价、强基计划、中外合作办学。
    changzhou_news_wechat_queries: list[str] = Field(
        default_factory=lambda: [
            "常州 高考 升学",
            "常州 高考 志愿填报",
            "常州 高考 招生 录取",
            "常州 高考 分数线",
            "常州 高三 一模 二模",
            "常州 强基计划 综合评价",
            "常州 高中 选科 升学规划",
            "常州 本科 专业 录取",
            "江苏 高校 招生 综合评价",
            "江苏 强基计划 招生 简章",
            "全国 高校 本科 招生 简章",
            "中外合作办学 高校 招生",
            "港澳高校 内地招生",
            "高校 专项计划 招生",
        ]
    )
    # 本地媒体公开列表页（本地宝/中吴网/化龙巷等）。
    changzhou_news_local_media_urls: list[str] = Field(
        default_factory=lambda: [
            "https://cz.bendibao.com/edu/",
            "https://www.cz001.com.cn/",
            "https://www.hualongxiang.com/",
        ]
    )
    # 单源单次抓取的最大条目数（防止单页过大）。
    changzhou_news_per_source_limit: int = Field(default=20, ge=1, le=100)
    video_data_provider: str = Field(default="disabled", pattern="^(disabled|tikhub)$")
    tikhub_api_key: str = ""
    tikhub_base_url: str = "https://api.tikhub.io"
    # 语音识别（ASR）服务：
    # - none：仅使用抖音自带字幕/画面文字，不做音频转写（默认，零依赖）。
    # - local-whisper：本地 faster-whisper 模型离线转写，无需任何 API key（中文可用）。
    # - doubao：豆包/火山语音识别，云端转写视频音频，不下载本地模型。
    transcription_provider: str = Field(
        default="none", pattern="^(none|local-whisper|doubao)$"
    )
    doubao_asr_api_key: str = ""
    doubao_asr_app_key: str = ""
    doubao_asr_access_key: str = ""
    doubao_asr_resource_id: str = "volc.bigasr.auc_turbo"
    doubao_asr_endpoint: str = (
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    )
    doubao_asr_model_name: str = "bigmodel"
    doubao_asr_language: str = "zh-CN"
    asr_audio_preprocess_enabled: bool = True
    ffmpeg_binary: str = "ffmpeg"
    whisper_model_size: str = Field(
        default="base", pattern="^(tiny|base|small|medium|large-v2|large-v3)$"
    )
    whisper_device: str = Field(default="cpu", pattern="^(cpu|auto)$")
    whisper_compute_type: str = Field(
        default="int8", pattern="^(int8|int8_float16|float16|float32)$"
    )
    whisper_language: str = "zh"  # 强制中文以提速；设为 "auto" 可自动检测语言
    whisper_model_dir: str = ""  # 可选：模型缓存目录，留空用默认 ~/.cache/huggingface
    # 文稿润色大模型：默认 rule（纯本地规则，离线可用、无需任何 key）。
    # 可选 doubao / deepseek / qwen / zhipu / kimi（均兼容 OpenAI /chat/completions 协议）。
    # 本项目不依赖 OpenAI；未配置对应 *_api_key 时，调用方自动回退到本地规则引擎。
    manuscript_provider: str = Field(
        default="rule", pattern="^(rule|doubao|deepseek|qwen|zhipu|kimi)$"
    )
    manuscript_model: str = "doubao-pro-32k"  # 历史兼容字段，实际模型以各 *_model 为准
    # 统一大模型接入（默认厂商）。可选：doubao | deepseek | qwen | zhipu | kimi | rule。
    llm_provider: str = Field(
        default="doubao", pattern="^(doubao|deepseek|qwen|zhipu|kimi|rule)$"
    )
    # 豆包 / 火山方舟
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = "doubao-pro-32k"
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    # 通义千问 / 阿里云百炼（OpenAI 兼容模式）
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    # 智谱 GLM
    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4-plus"
    # Kimi / 月之暗面
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"
    # 视觉/多模态大模型（用于把公众号里的"图片表格"OCR 成结构化数据 → 凭他教育知识卡片）。
    # 与文生文 llm_provider 分离：图片表格识别需要支持 image_url 的视觉模型。
    # 可选：doubao | openai | deepseek(不推荐) | 留空 = 不启用（图片表格仅去水印后原样嵌入）。
    vision_llm_provider: str = Field(
        default="", pattern="^(doubao|openai|qwen|zhipu|kimi|rule|)$"
    )
    vision_llm_api_key: str = ""
    vision_llm_base_url: str = ""
    vision_llm_model: str = ""
    # HuggingFace 镜像与下载设置（仅本地 Whisper 模型首次下载时需要）。
    # 国内沙箱直连 huggingface.co 超时，可用镜像 hf-mirror.com 并禁用 xet 存储。
    hf_endpoint: str = ""  # 例：https://hf-mirror.com；留空用官方源
    hf_hub_disable_xet: bool = False  # 某些镜像不支持 xet 存储时设为 True


@lru_cache
def get_settings() -> Settings:
    return Settings()
