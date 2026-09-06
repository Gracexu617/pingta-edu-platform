"""统一的多模型 LLM 客户端（OpenAI 兼容 /chat/completions）。

本项目不依赖 OpenAI。默认支持：豆包(火山方舟) / DeepSeek / 通义千问 / 智谱GLM / Kimi。
所有厂商均兼容 OpenAI 的 chat/completions 协议，因此可用同一套调用逻辑。

设计原则：
- 未配置对应 *_api_key，或网络/解析异常时，返回 None。调用方务必回退到本地规则引擎。
- 绝不让任何外部模型调用阻断主流程；离线/无 key 场景下平台必须照常工作。
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# 各厂商默认接入点（可用 .env 中的 *_BASE_URL 覆盖）
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
    },
}


def _resolve_config(settings, provider: str) -> Optional[dict]:
    """从 settings 解析某厂商的 base_url / api_key / model；不可用则返回 None。"""
    provider = (provider or "").lower()
    if provider in ("rule", "none", ""):
        return None
    defaults = PROVIDER_DEFAULTS.get(provider)
    prefix = provider
    api_key = getattr(settings, f"{prefix}_api_key", "") or ""
    if not api_key:
        return None
    if defaults is None:
        # 未知厂商：尝试用 provider 名作前缀读取通用配置
        base_url = getattr(settings, f"{prefix}_base_url", "") or ""
        model = getattr(settings, f"{prefix}_model", "") or ""
        if not base_url:
            return None
        return {"base_url": base_url.rstrip("/"), "api_key": api_key, "model": model}
    base_url = getattr(settings, f"{prefix}_base_url", "") or defaults["base_url"]
    model = getattr(settings, f"{prefix}_model", "") or defaults["model"]
    return {"base_url": base_url.rstrip("/"), "api_key": api_key, "model": model}


async def call_llm(
    settings,
    provider: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    temperature: float = 0.3,
    timeout: float = 60.0,
) -> Optional[str]:
    """调用一次 OpenAI 兼容对话补全，返回纯文本或 None（未配置 / 失败 / 异常）。"""
    cfg = _resolve_config(settings, provider)
    if cfg is None:
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            if resp.status_code >= 400:
                logger.warning("LLM[%s] 调用失败: HTTP %s", provider, resp.status_code)
                return None
            payload = resp.json()
            if not isinstance(payload, dict):
                return None
            content = (
                payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return content.strip() if isinstance(content, str) else ""
    except Exception:  # noqa: BLE001 - 任何网络/解析异常都回退规则引擎
        logger.warning("LLM[%s] 调用异常，回退规则引擎", provider, exc_info=True)
        return None


async def call_vision_llm(
    settings,
    provider: str,
    prompt: str,
    *,
    image_bytes: bytes,
    image_mime: str = "image/png",
    temperature: float = 0.2,
    timeout: float = 60.0,
) -> Optional[str]:
    """调用支持视觉的 OpenAI 兼容多模态模型，传入一张图片 + 文本指令，返回模型文本。

    用于把公众号文章里的「图片表格」OCR 成结构化数据。未配置 / 失败 / 异常均返回 None，
    调用方应回退到「去水印后原样嵌入图片」策略。
    """
    cfg = _resolve_config(settings, provider)
    if cfg is None:
        return None

    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{image_mime};base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": messages,
                    "temperature": temperature,
                },
            )
            if resp.status_code >= 400:
                logger.warning("VisionLLM[%s] 调用失败: HTTP %s", provider, resp.status_code)
                return None
            payload = resp.json()
            if not isinstance(payload, dict):
                return None
            content = (
                payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            )
            return content.strip() if isinstance(content, str) else ""
    except Exception:  # noqa: BLE001
        logger.warning("VisionLLM[%s] 调用异常，回退规则", provider, exc_info=True)
        return None
