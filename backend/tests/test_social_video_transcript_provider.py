from typing import Any

import httpx
import pytest

from app.services.social_video_transcript_provider import (
    AudioPreprocessError,
    AudioTranscriptionError,
    DoubaoAsrTranscriber,
    TikHubDouyinTranscriptProvider,
    build_social_video_transcript_provider,
)


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_prefers_caption() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "caption": "大家好，嗯高考志愿填报先看分数",
                    "desc": "短标题",
                }
            }
        }

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_get=fake_get,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "TikHub字幕"
    assert extraction.text == "大家好，嗯高考志愿填报先看分数"


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_ignores_desc_and_title() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "caption": "",
                    "video_text": [],
                    "desc": "高考志愿填报指南",
                    "item_title": "高考标题",
                }
            }
        }

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_get=fake_get,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "未配置语音识别服务（已停用 OpenAI，当前仅支持抖音字幕）"
    assert extraction.text == ""


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_transcribes_audio_when_no_video_text() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "caption": "",
                    "video_text": [],
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    async def fake_download(url: str) -> bytes:
        assert url == "https://media.example/video.mp4"
        return b"video-bytes"

    async def fake_transcribe(media_bytes: bytes, model: str) -> str:
        assert media_bytes == b"video-bytes"
        assert model == "doubao"
        return "大家好，嗯高考志愿填报要先看分数"

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="doubao",
        http_get=fake_get,
        http_download=fake_download,
        audio_transcriber=fake_transcribe,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "豆包/火山语音转文字"
    assert extraction.text == "大家好，嗯高考志愿填报要先看分数"


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_reports_missing_transcription_config() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_get=fake_get,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "未配置语音识别服务（已停用 OpenAI，当前仅支持抖音字幕）"
    assert extraction.text == ""


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_reports_transcription_error() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    async def fake_download(url: str) -> bytes:
        return b"video-bytes"

    async def fake_transcribe(media_bytes: bytes, model: str) -> str:
        raise AudioTranscriptionError("豆包额度不足", "quota exceeded")

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="doubao",
        http_get=fake_get,
        http_download=fake_download,
        audio_transcriber=fake_transcribe,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "豆包额度不足"
    assert extraction.text == ""


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_reports_download_failure() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    async def fake_download(url: str) -> bytes:
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="doubao",
        http_get=fake_get,
        http_download=fake_download,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "视频下载失败"
    assert extraction.text == ""


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_reports_oversized_video() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    async def fake_download(url: str) -> bytes:
        raise ValueError("media file exceeds transcription size limit")

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="doubao",
        http_get=fake_get,
        http_download=fake_download,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "视频文件过大，待分段转写"
    assert extraction.text == ""


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_returns_none_on_http_error() -> None:
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = httpx.Request("GET", url)
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("failed", request=request, response=response)

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        http_get=fake_get,
    )

    assert await provider.extract("https://www.douyin.com/video/123") is None


@pytest.mark.asyncio
async def test_tikhub_transcript_provider_treats_hashtag_only_caption_as_missing() -> None:
    # 只有话题标签的“伪字幕”应视为无效，回退到音频转写（本地 Whisper）。
    async def fake_get(
        url: str,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "data": {
                "aweme_detail": {
                    "caption": "#峰学未来#专业选择的重要性 #高考",
                    "video": {"play_addr": {"url_list": ["https://media.example/video.mp4"]}},
                }
            }
        }

    async def fake_download(url: str) -> bytes:
        return b"video-bytes"

    async def fake_transcribe(media_bytes: bytes, model: str) -> str:
        assert media_bytes == b"video-bytes"
        return "计算机专业是总称，包含计算机科学与技术等"

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="local-whisper",
        http_get=fake_get,
        http_download=fake_download,
        audio_transcriber=fake_transcribe,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.source == "本地Whisper语音转文字"
    assert "计算机" in extraction.text


@pytest.mark.asyncio
async def test_build_injects_local_whisper_transcriber() -> None:
    from app.core.config import Settings

    settings = Settings(
        video_data_provider="tikhub",
        tikhub_api_key="test-key",
        transcription_provider="local-whisper",
    )
    provider = build_social_video_transcript_provider(settings)

    assert isinstance(provider, TikHubDouyinTranscriptProvider)
    assert provider._audio_transcriber is not None


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_posts_base64_audio_and_reads_text() -> None:
    captured: dict[str, Any] = {}

    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json_body
        return {"result": {"text": "高考志愿填报先看专业"}}

    transcriber = DoubaoAsrTranscriber(
        api_key="doubao-key",
        endpoint="https://example.test/asr",
        http_post=fake_post,
    )

    text = await transcriber.transcribe(b"ID3audio")

    assert text == "高考志愿填报先看专业"
    assert captured["url"] == "https://example.test/asr"
    assert captured["headers"]["X-Api-Key"] == "doubao-key"
    assert captured["headers"]["X-Api-Resource-Id"] == "volc.bigasr.auc_turbo"
    assert captured["body"]["audio"]["format"] == "mp3"
    assert captured["body"]["audio"]["data"] == "SUQzYXVkaW8="


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_uses_preprocessed_wav_audio() -> None:
    captured: dict[str, Any] = {}

    async def fake_preprocess(media_bytes: bytes) -> bytes:
        assert media_bytes == b"\x00\x00\x00\x20ftypisom-video"
        return b"RIFFxxxxWAVEaudio"

    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        captured["body"] = json_body
        return {"result": {"text": "高考选科要看专业要求"}}

    transcriber = DoubaoAsrTranscriber(
        api_key="doubao-key",
        audio_preprocessor=fake_preprocess,
        http_post=fake_post,
    )

    text = await transcriber.transcribe(b"\x00\x00\x00\x20ftypisom-video")

    assert text == "高考选科要看专业要求"
    assert captured["body"]["audio"]["format"] == "wav"
    assert captured["body"]["audio"]["data"] == "UklGRnh4eHhXQVZFYXVkaW8="


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_retries_transient_network_errors() -> None:
    calls = 0

    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("temporary network error")
        return {"result": {"text": "高考志愿填报要看位次"}}

    transcriber = DoubaoAsrTranscriber(api_key="doubao-key", http_post=fake_post)

    assert await transcriber.transcribe(b"ID3audio") == "高考志愿填报要看位次"
    assert calls == 3


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_reports_preprocess_failure() -> None:
    async def fake_preprocess(media_bytes: bytes) -> bytes:
        raise AudioPreprocessError("音频预处理失败", "invalid media")

    transcriber = DoubaoAsrTranscriber(
        api_key="doubao-key",
        audio_preprocessor=fake_preprocess,
    )

    with pytest.raises(AudioTranscriptionError) as exc_info:
        await transcriber.transcribe(b"bad-video")

    assert exc_info.value.source == "音频预处理失败"


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_supports_utterance_result() -> None:
    async def fake_post(
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> dict[str, Any]:
        return {"result": {"utterances": [{"text": "第一句"}, {"text": "第二句"}]}}

    transcriber = DoubaoAsrTranscriber(api_key="doubao-key", http_post=fake_post)

    assert await transcriber.transcribe(b"RIFFxxxxWAVE") == "第一句\n第二句"


@pytest.mark.asyncio
async def test_doubao_asr_transcriber_requires_credentials() -> None:
    transcriber = DoubaoAsrTranscriber()

    with pytest.raises(AudioTranscriptionError) as exc_info:
        await transcriber.transcribe(b"audio")

    assert exc_info.value.source == "豆包/火山语音识别未配置"


@pytest.mark.asyncio
async def test_build_injects_doubao_transcriber() -> None:
    from app.core.config import Settings

    settings = Settings(
        video_data_provider="tikhub",
        tikhub_api_key="test-key",
        transcription_provider="doubao",
        doubao_asr_api_key="doubao-key",
    )
    provider = build_social_video_transcript_provider(settings)

    assert isinstance(provider, TikHubDouyinTranscriptProvider)
    assert provider._audio_transcriber is not None


@pytest.mark.asyncio
async def test_audio_download_failure_is_not_masked_by_subtitle() -> None:
    """回归：音频下载失败时，真实故障原因必须冒出来，不能被「字幕」回退掩盖。

    之前 extract() 在 _transcribe_audio 返回空文本时会直接回退到 TikHub 字幕，
    导致「视频下载失败」这类真实故障被吞掉，UI 误以为只是没字幕/内容问题。
    """
    caption_payload: dict[str, Any] = {
        "data": {
            "aweme_detail": {
                "video": {"play_addr": {"url_list": ["https://x/v.mp4"]}},
                "caption": "这是一段有效字幕内容",
            }
        }
    }

    async def fake_get(url, headers, params):
        return caption_payload

    async def fake_download(url):
        raise httpx.ConnectError("download boom")

    async def dummy_transcribe(media_bytes, provider):
        return "should-not-be-called"

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="local-whisper",
        http_get=fake_get,
        http_download=fake_download,
        audio_transcriber=dummy_transcribe,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.text == "这是一段有效字幕内容"
    assert "音频提取失败" in extraction.source
    assert "下载失败" in extraction.source


@pytest.mark.asyncio
async def test_audio_success_still_prefers_real_speech() -> None:
    """回归：音频成功转写出有效语音时，仍应优先返回音频结果（不被字幕掩盖）。"""
    caption_payload: dict[str, Any] = {
        "data": {
            "aweme_detail": {
                "video": {"play_addr": {"url_list": ["https://x/v.mp4"]}},
                "caption": "这只是标题字幕",
            }
        }
    }

    async def fake_get(url, headers, params):
        return caption_payload

    async def fake_download(url):
        return b"\x00\x00\x00\x20ftypisom" + b"\x00" * 2000

    async def fake_transcribe(media_bytes, provider):
        return "真实语音识别出来的内容"

    provider = TikHubDouyinTranscriptProvider(
        api_key="test-key",
        base_url="https://api.tikhub.io",
        transcription_provider="local-whisper",
        http_get=fake_get,
        http_download=fake_download,
        audio_transcriber=fake_transcribe,
    )

    extraction = await provider.extract("https://www.douyin.com/video/123")

    assert extraction is not None
    assert extraction.text == "真实语音识别出来的内容"
    assert extraction.source == "本地Whisper语音转文字"
    assert "音频提取失败" not in extraction.source
