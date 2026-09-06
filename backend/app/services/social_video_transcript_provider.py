import asyncio
import base64
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

# 去掉话题标签（#xxx）与空白后若所剩无几，视为“伪字幕”，应回退到音频转写。
_TAG_STRIP = re.compile(r"#[\w一-鿿]+|#|\s")


def _has_real_text(value: str) -> bool:
    return bool(_TAG_STRIP.sub("", value).strip())

HttpGet = Callable[[str, dict[str, str], dict[str, Any] | None], Awaitable[dict[str, Any]]]
HttpPostJson = Callable[[str, dict[str, str], dict[str, Any]], Awaitable[dict[str, Any]]]
HttpDownload = Callable[[str], Awaitable[bytes]]
AudioTranscriber = Callable[[bytes, str], Awaitable[str]]
AudioPreprocessor = Callable[[bytes], Awaitable[bytes]]
MAX_TRANSCRIPTION_BYTES = 120 * 1024 * 1024
MAX_PREPROCESSED_AUDIO_BYTES = 60 * 1024 * 1024
MEDIA_REQUEST_HEADERS = {
    "Accept": "*/*",
    "Referer": "https://www.douyin.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}


@dataclass(frozen=True, slots=True)
class TranscriptExtraction:
    text: str
    source: str


class AudioTranscriptionError(Exception):
    def __init__(self, source: str, message: str) -> None:
        super().__init__(message)
        self.source = source


class AudioPreprocessError(Exception):
    def __init__(self, source: str, message: str) -> None:
        super().__init__(message)
        self.source = source


class SocialVideoTranscriptProvider(Protocol):
    async def extract(
        self,
        original_url: str,
        *,
        play_url: str = "",
    ) -> TranscriptExtraction | None: ...


class DisabledSocialVideoTranscriptProvider:
    async def extract(
        self,
        original_url: str,
        *,
        play_url: str = "",
    ) -> TranscriptExtraction | None:
        return None


class LocalWhisperTranscriber:
    """离线语音转写：基于 faster-whisper，无需任何 API key。

    首次调用会按需从 HuggingFace 下载模型权重（约 140MB，仅一次），
    之后常驻内存。推理为 CPU 阻塞操作，统一丢到线程池执行，避免卡住事件循环。
    """

    def __init__(
        self,
        *,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "zh",
        model_dir: str = "",
    ) -> None:
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model_dir = model_dir or None
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:  # pragma: no cover
                raise AudioTranscriptionError(
                    "本地Whisper未安装", "请执行 pip install faster-whisper"
                ) from exc
            try:
                self._model = WhisperModel(
                    self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                    download_root=self._model_dir,
                )
            except Exception as exc:  # noqa: BLE001
                raise AudioTranscriptionError(
                    "本地Whisper模型加载失败", str(exc)[:200]
                ) from exc
        return self._model

    @staticmethod
    def _guess_audio_suffix(media_bytes: bytes) -> str:
        """根据文件魔数猜测容器格式，避免把 wav/aiff 等误判成 mp4 导致解码成乱码。"""
        return _guess_media_suffix(media_bytes)

    def _transcribe_sync(self, media_bytes: bytes) -> str:
        model = self._ensure_model()
        suffix = self._guess_audio_suffix(media_bytes)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(media_bytes)
            tmp_path = tmp.name
        try:
            segments, _info = model.transcribe(
                tmp_path,
                language=self._language if self._language != "auto" else None,
                beam_size=5,
                vad_filter=True,
            )
            text = "".join(segment.text for segment in segments).strip()
            if text:
                return text
            # Some Douyin clips mix speech with music; VAD can be too aggressive.
            segments, _info = model.transcribe(
                tmp_path,
                language=self._language if self._language != "auto" else None,
                beam_size=5,
                vad_filter=False,
            )
            return "".join(segment.text for segment in segments).strip()
        except Exception as exc:  # noqa: BLE001
            raise AudioTranscriptionError("本地Whisper转写失败", str(exc)[:200]) from exc
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def transcribe(self, media_bytes: bytes, model: str = "") -> str:
        return await asyncio.to_thread(self._transcribe_sync, media_bytes)


class FfmpegAudioPreprocessor:
    """把视频/音频临时转为 ASR 更稳的 16k 单声道 wav。"""

    def __init__(self, *, ffmpeg_binary: str = "ffmpeg") -> None:
        self._ffmpeg_binary = ffmpeg_binary

    async def preprocess(self, media_bytes: bytes) -> bytes:
        return await asyncio.to_thread(self._preprocess_sync, media_bytes)

    def _preprocess_sync(self, media_bytes: bytes) -> bytes:
        ffmpeg_path = shutil.which(self._ffmpeg_binary)
        if not ffmpeg_path:
            raise AudioPreprocessError("音频预处理不可用", "未找到 ffmpeg")

        input_suffix = _guess_media_suffix(media_bytes)
        input_path = ""
        output_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=input_suffix, delete=False) as src:
                src.write(media_bytes)
                input_path = src.name
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as dst:
                output_path = dst.name
            command = [
                ffmpeg_path,
                "-y",
                "-i",
                input_path,
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                output_path,
            ]
            completed = subprocess.run(  # noqa: S603
                command,
                check=False,
                capture_output=True,
                timeout=120,
            )
            if completed.returncode != 0:
                error = completed.stderr.decode("utf-8", errors="ignore")[-200:]
                raise AudioPreprocessError("音频预处理失败", error)
            audio_bytes = _read_file_bytes(output_path)
            if not audio_bytes:
                raise AudioPreprocessError("音频预处理失败", "ffmpeg 输出为空")
            if len(audio_bytes) > MAX_PREPROCESSED_AUDIO_BYTES:
                raise AudioPreprocessError("音频文件过大，待分段转写", "wav too large")
            return audio_bytes
        except subprocess.TimeoutExpired as exc:
            raise AudioPreprocessError("音频预处理超时", str(exc)[:120]) from exc
        finally:
            for path in (input_path, output_path):
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass


class DoubaoAsrTranscriber:
    """豆包/火山语音识别云端转写。

    只在用户点击「提取转写」后运行。媒体字节通过 HTTPS 发给 ASR 服务，
    本机不下载 Whisper 模型，也不保存音视频文件。
    """

    def __init__(
        self,
        *,
        api_key: str = "",
        app_key: str = "",
        access_key: str = "",
        resource_id: str = "volc.bigasr.auc_turbo",
        endpoint: str = (
            "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
        ),
        model_name: str = "bigmodel",
        language: str = "zh-CN",
        audio_preprocessor: AudioPreprocessor | None = None,
        http_post: HttpPostJson | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._app_key = app_key.strip()
        self._access_key = access_key.strip()
        self._resource_id = resource_id.strip()
        self._endpoint = endpoint.strip()
        self._model_name = model_name.strip() or "bigmodel"
        self._language = language.strip() or "zh-CN"
        self._audio_preprocessor = audio_preprocessor
        self._http_post = http_post or default_http_post_json

    async def transcribe(self, media_bytes: bytes, model: str = "") -> str:
        if not self._has_credentials:
            raise AudioTranscriptionError(
                "豆包/火山语音识别未配置",
                "请在 backend/.env 设置 DOUBAO_ASR_API_KEY，或设置旧版 "
                "DOUBAO_ASR_APP_KEY + DOUBAO_ASR_ACCESS_KEY",
            )
        headers = self._headers()
        prepared_bytes = await self._prepare_audio(media_bytes)
        body: dict[str, Any] = {
            "user": {"uid": "education-intel-platform"},
            "audio": {
                "format": _guess_doubao_audio_format(prepared_bytes),
                "codec": "raw",
                "data": base64.b64encode(prepared_bytes).decode("ascii"),
            },
            "request": {
                "model_name": self._model_name,
                "enable_punc": True,
                "language": self._language,
            },
        }
        payload = await self._post_with_retry(headers, body)
        if not _is_doubao_success(payload):
            raise AudioTranscriptionError(
                "豆包/火山语音识别失败",
                _doubao_error_message(payload)[:200],
            )
        return _extract_doubao_text(payload)

    async def _prepare_audio(self, media_bytes: bytes) -> bytes:
        if self._audio_preprocessor is None:
            return media_bytes
        try:
            return await self._audio_preprocessor(media_bytes)
        except AudioPreprocessError as exc:
            if exc.source == "音频预处理不可用":
                logger.warning("asr_audio_preprocess_unavailable", extra={"error": str(exc)})
                return media_bytes
            raise AudioTranscriptionError(exc.source, str(exc)[:200]) from exc

    async def _post_with_retry(
        self,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return await self._http_post(self._endpoint, headers, body)
            except AudioTranscriptionError:
                raise
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise AudioTranscriptionError(
            "豆包/火山语音识别网络失败",
            str(last_error or "request failed")[:200],
        )

    @property
    def _has_credentials(self) -> bool:
        return bool(self._api_key or (self._app_key and self._access_key))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": self._resource_id,
        }
        if self._api_key:
            headers["X-Api-Key"] = self._api_key
            return headers
        headers["X-Api-App-Key"] = self._app_key
        headers["X-Api-Access-Key"] = self._access_key
        return headers


async def default_http_get(
    url: str,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def default_http_post_json(
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json=json_body)
        if response.status_code in (401, 403):
            raise AudioTranscriptionError("豆包/火山语音识别鉴权失败", _error_message(response))
        if response.status_code == 429:
            raise AudioTranscriptionError("豆包/火山语音识别额度不足", _error_message(response))
        response.raise_for_status()
        return response.json()


async def default_http_download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=MEDIA_REQUEST_HEADERS) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_TRANSCRIPTION_BYTES:
                    raise ValueError("media file exceeds transcription size limit")
                chunks.append(chunk)
    return b"".join(chunks)


# 未配置任何语音识别服务时的统一提示（已停用 OpenAI）。
TRANSCRIPTION_DISABLED_MESSAGE = "未配置语音识别服务（已停用 OpenAI，当前仅支持抖音字幕）"


def _transcription_source_label(provider: str) -> str:
    if provider == "doubao":
        return "豆包/火山语音转文字"
    if provider == "local-whisper":
        return "本地Whisper语音转文字"
    return ""


def _read_file_bytes(path: str) -> bytes:
    """读取本地媒体文件字节（用于在本地已下载好的文件上做离线转写）。"""
    with open(path, "rb") as fh:
        return fh.read()


async def _transcribe_bytes(
    media_bytes: bytes,
    audio_transcriber: AudioTranscriber | None,
    transcription_provider: str,
    source_label: str,
) -> TranscriptExtraction:
    """统一的字节级转写：把媒体字节喂给 Whisper，返回识别结果。
    本地文件直转与上传文件直转共用此逻辑，完全不依赖 TikHub。
    媒体仅在内存中走一遭，转写完成即丢弃，仅保留文字结果。"""
    if not audio_transcriber or transcription_provider == "none":
        hint = "TRANSCRIPTION_PROVIDER=local-whisper"
        if source_label.startswith("豆包"):
            hint = "TRANSCRIPTION_PROVIDER=doubao，并填写 DOUBAO_ASR_API_KEY"
        source = (
            f"未配置{source_label or '语音识别'}"
            f"（缺少转写器；请在 .env 设置 {hint}）"
        )
        return TranscriptExtraction(
            text="",
            source=source,
        )
    if not media_bytes:
        return TranscriptExtraction(text="", source="媒体数据为空")
    if len(media_bytes) > MAX_TRANSCRIPTION_BYTES:
        return TranscriptExtraction(text="", source="媒体文件过大，待分段转写")
    try:
        text = await audio_transcriber(media_bytes, transcription_provider)
    except AudioTranscriptionError as exc:
        return TranscriptExtraction(text="", source=exc.source)
    except Exception as exc:  # noqa: BLE001
        return TranscriptExtraction(
            text="", source=f"{source_label}转写失败：{str(exc)[:120]}"
        )
    if not text:
        return TranscriptExtraction(text="", source="语音转文字无结果")
    return TranscriptExtraction(text=text, source=source_label or "本地语音转文字")


class TikHubDouyinTranscriptProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        transcription_provider: str = "none",
        http_get: HttpGet = default_http_get,
        http_download: HttpDownload = default_http_download,
        audio_transcriber: AudioTranscriber | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._transcription_provider = transcription_provider
        self._transcription_source = _transcription_source_label(transcription_provider)
        self._http_get = http_get
        self._http_download = http_download
        self._audio_transcriber = audio_transcriber

    async def extract(
        self, original_url: str, *, play_url: str = ""
    ) -> TranscriptExtraction | None:
        if not original_url:
            return None
        payload = None
        # 优先尝试 TikHub 获取视频详情（含字幕 + 播放地址）
        if self._api_key:
            try:
                payload = await self._http_get(
                    f"{self._base_url}/api/v1/douyin/app/v3/fetch_one_video_by_share_url",
                    {"Authorization": f"Bearer {self._api_key}"},
                    {"share_url": original_url},
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "tikhub_video_detail_failed",
                    extra={"error": str(exc)[:120]},
                )
                # TikHub 失败时：优先使用已存储的 play_url，其次尝试从分享链接解析
                if self._transcription_provider and self._transcription_provider != "none":
                    if play_url:
                        payload = {
                            "data": {
                                "aweme_detail": {
                                    "video": {
                                        "play_addr": {"url_list": [play_url]}
                                    }
                                }
                            }
                        }
                    else:
                        payload = await self._resolve_video_from_share_url(original_url)

        if payload is None:
            # 无 API key 且无备用方案时才返回 None
            return None

        audio_enabled = bool(
            self._transcription_provider and self._transcription_provider != "none"
        )
        # 优先真实语音识别：用户要求提取「视频内真实语音内容」而非标题/描述，
        # TikHub 字幕（caption/video_text）常仅为视频标题或话题标签，故作为回退。
        audio_result = None
        if audio_enabled:
            audio_result = await self._transcribe_audio(payload)
            if audio_result.text:
                return audio_result
        extracted = _extract_transcript(payload)
        if extracted is not None:
            # 若音频提取路径发生了真正的故障（下载/转写异常/文件过大），
            # 把原因带出来，避免被「字幕」回退悄悄掩盖，让 UI 能显示真实失败原因。
            reason = _audio_hard_failure_reason(audio_result)
            if reason:
                return TranscriptExtraction(
                    text=extracted.text,
                    source=f"{extracted.source}（音频提取失败：{reason}）",
                )
            return extracted
        # 字幕也没有：返回音频侧提示（更贴近“真实语音”诉求），或 None
        if audio_result is not None and audio_result.source:
            return audio_result
        return await self._transcribe_audio(payload)

    async def extract_from_local(self, path: str) -> TranscriptExtraction:
        """方案 C：对本地已下载的媒体文件做离线转写，完全不依赖 TikHub。
        媒体仅在内存/临时目录中走一遭，转写完成即丢弃，仅保留文字结果。"""
        try:
            media_bytes = _read_file_bytes(path)
        except OSError as exc:
            return TranscriptExtraction(
                text="", source=f"本地文件读取失败：{exc.strerror or exc}"
            )
        return await _transcribe_bytes(
            media_bytes,
            self._audio_transcriber,
            self._transcription_provider,
            self._transcription_source,
        )

    async def _resolve_video_from_share_url(
        self, share_url: str
    ) -> dict[str, Any] | None:
        """TikHub 不可用时，尝试从抖音分享链接解析出视频播放地址。

        通过跟随重定向链拿到抖音视频页，再从中提取 video_id，
        最后构造一个含 play_addr 的伪 payload 供 _transcribe_audio 使用。
        """
        video_id = self._extract_video_id(share_url)
        if not video_id:
            logger.warning("could_not_extract_video_id", extra={"url": share_url[:80]})
            return None
        try:
            # 尝试抖音 Web API 获取视频详情（无需 TikHub）
            detail_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
            resp = await self._http_get(
                detail_url,
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
                    "Safari/537.36",
                    "Referer": "https://www.douyin.com/",
                },
                None,
            )
            if resp and isinstance(resp, dict):
                aweme_detail = resp.get("aweme_detail") or resp
                if isinstance(aweme_detail, dict):
                    return {"data": {"aweme_detail": aweme_detail}}
        except httpx.HTTPError as exc:
            logger.warning(
                "douyin_web_api_failed",
                extra={"video_id": video_id, "error": str(exc)[:120]},
            )
        except Exception as exc:
            logger.warning(
                "resolve_share_url_failed",
                extra={"video_id": video_id, "error": str(exc)[:120]},
            )
        return None

    @staticmethod
    def _extract_video_id(url: str) -> str | None:
        """从抖音分享链接中提取 video ID。"""
        import re
        # 匹配 /video/数字 或 mid=数字
        m = re.search(r"/video/(\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"(?:mid|video_id)[=:]*(\d+)", url)
        if m:
            return m.group(1)
        return None

    async def _transcribe_audio(self, payload: dict[str, Any]) -> TranscriptExtraction:
        # 未启用任何语音识别服务：只依赖抖音自带字幕（上面 extract 已优先使用），
        # 没有字幕的视频无法转写，给出清晰提示，绝不回退到 OpenAI。
        if not self._transcription_provider or self._transcription_provider == "none":
            return TranscriptExtraction(text="", source=TRANSCRIPTION_DISABLED_MESSAGE)
        play_url = _extract_play_url(payload)
        if not play_url:
            return TranscriptExtraction(text="", source="未获取到视频播放地址")
        try:
            media_bytes = await self._http_download(play_url)
        except httpx.HTTPError as exc:
            logger.warning(
                "social_video_audio_download_failed",
                extra={"error": str(exc)[:120]},
            )
            return TranscriptExtraction(text="", source="视频下载失败")
        except ValueError as exc:
            logger.warning(
                "social_video_audio_too_large",
                extra={"error": str(exc)[:120]},
            )
            return TranscriptExtraction(text="", source="视频文件过大，待分段转写")

        if self._audio_transcriber is None:
            return TranscriptExtraction(
                text="",
                source=f"未配置{self._transcription_source or '语音识别'}（缺少转写器）",
            )
        try:
            text = await self._audio_transcriber(media_bytes, self._transcription_provider)
        except AudioTranscriptionError as exc:
            logger.warning(
                "social_video_audio_transcription_failed",
                extra={"source": exc.source, "error": str(exc)[:120]},
            )
            return TranscriptExtraction(text="", source=exc.source)
        except httpx.HTTPError as exc:
            logger.warning(
                "social_video_audio_transcription_failed",
                extra={"source": f"{self._transcription_source}转写失败", "error": str(exc)[:120]},
            )
            return TranscriptExtraction(text="", source=f"{self._transcription_source}转写失败")
        if not text:
            return TranscriptExtraction(text="", source="语音转文字无结果")
        return TranscriptExtraction(text=text, source=self._transcription_source or "语音转文字")


def _build_audio_transcriber(settings: Settings) -> AudioTranscriber | None:
    # 应用 HuggingFace 镜像/下载设置（仅本地 Whisper 模型首次下载时需要）。
    if settings.hf_endpoint:
        os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)
    if settings.hf_hub_disable_xet:
        os.environ["HF_HUB_DISABLE_XET"] = "1"
    if settings.transcription_provider == "doubao":
        audio_preprocessor = None
        if settings.asr_audio_preprocess_enabled:
            audio_preprocessor = FfmpegAudioPreprocessor(
                ffmpeg_binary=settings.ffmpeg_binary
            ).preprocess
        doubao = DoubaoAsrTranscriber(
            api_key=settings.doubao_asr_api_key or settings.doubao_api_key,
            app_key=settings.doubao_asr_app_key,
            access_key=settings.doubao_asr_access_key,
            resource_id=settings.doubao_asr_resource_id,
            endpoint=settings.doubao_asr_endpoint,
            model_name=settings.doubao_asr_model_name,
            language=settings.doubao_asr_language,
            audio_preprocessor=audio_preprocessor,
        )
        return doubao.transcribe
    if settings.transcription_provider == "local-whisper":
        whisper = LocalWhisperTranscriber(
            model_size=settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            language=settings.whisper_language,
            model_dir=settings.whisper_model_dir,
        )
        return whisper.transcribe
    return None


def build_social_video_transcript_provider(settings: Settings) -> SocialVideoTranscriptProvider:
    if settings.video_data_provider == "tikhub" and settings.tikhub_api_key:
        return TikHubDouyinTranscriptProvider(
            api_key=settings.tikhub_api_key,
            base_url=settings.tikhub_base_url,
            transcription_provider=settings.transcription_provider,
            audio_transcriber=_build_audio_transcriber(settings),
        )
    return DisabledSocialVideoTranscriptProvider()


class LocalFileTranscriptProvider:
    """纯本地文件转写提供方：不依赖 TikHub，可独立使用。
    适用于：断网/未充值 TikHub 时，对本地已下载的抖音音频/视频做语音转文字。"""

    def __init__(
        self,
        *,
        transcription_provider: str = "none",
        audio_transcriber: AudioTranscriber | None = None,
    ) -> None:
        self._transcription_provider = transcription_provider
        self._transcription_source = _transcription_source_label(transcription_provider)
        self._audio_transcriber = audio_transcriber

    async def extract_from_local(self, path: str) -> TranscriptExtraction:
        try:
            media_bytes = _read_file_bytes(path)
        except OSError as exc:
            return TranscriptExtraction(
                text="", source=f"本地文件读取失败：{exc.strerror or exc}"
            )
        return await _transcribe_bytes(
            media_bytes,
            self._audio_transcriber,
            self._transcription_provider,
            self._transcription_source,
        )

    async def extract_from_bytes(self, media_bytes: bytes) -> TranscriptExtraction:
        return await _transcribe_bytes(
            media_bytes,
            self._audio_transcriber,
            self._transcription_provider,
            self._transcription_source,
        )


def build_local_file_transcript_provider(settings: Settings) -> LocalFileTranscriptProvider | None:
    """构建本地文件转写提供方；若未启用本地 Whisper 则返回 None（表示本地转写未启用）。"""
    audio_transcriber = _build_audio_transcriber(settings)
    if audio_transcriber is None:
        return None
    return LocalFileTranscriptProvider(
        transcription_provider=settings.transcription_provider,
        audio_transcriber=audio_transcriber,
    )


_AUDIO_HARD_FAILURE_MARKERS = (
    "下载失败",
    "转写失败",
    "文件过大",
    "未配置",
    "鉴权失败",
    "额度不足",
)


def _audio_hard_failure_reason(audio_result: TranscriptExtraction | None) -> str | None:
    """若音频提取路径发生了真正的故障（下载/转写异常/文件过大），返回其原因文案；
    若是「无有效语音」（属正常内容特征，非故障）或 None，则返回 None。

    用途：extract() 在音频提取失败后可能回退到 TikHub 字幕，若直接返回字幕，
    会把「下载失败/转写失败」这类真实故障掩盖掉，导致 UI 误以为只是没字幕、
    或误以为「转写没成功是内容问题」。把真实原因带出来，UI 才能正确显示。
    """
    if audio_result is None or not audio_result.source:
        return None
    for marker in _AUDIO_HARD_FAILURE_MARKERS:
        if marker in audio_result.source:
            return audio_result.source
    return None


def _extract_transcript(payload: dict[str, Any]) -> TranscriptExtraction | None:
    detail = _extract_aweme_detail(payload)
    if not detail:
        return None

    for key, source in (
        ("caption", "TikHub字幕"),
        ("video_text", "TikHub视频文字"),
    ):
        text = _stringify_text(detail.get(key))
        # 只有“话题标签/空白”的伪字幕（如 #峰学未来#专业选择）视为无效，回退音频转写。
        if text and _has_real_text(text):
            return TranscriptExtraction(text=text, source=source)
    return None


def _extract_aweme_detail(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data", payload)
    if isinstance(data, dict) and isinstance(data.get("aweme_detail"), dict):
        return data["aweme_detail"]
    if isinstance(data, dict) and isinstance(data.get("aweme_info"), dict):
        return data["aweme_info"]
    return data if isinstance(data, dict) else {}


def _extract_play_url(payload: dict[str, Any]) -> str:
    detail = _extract_aweme_detail(payload)
    video = detail.get("video") if isinstance(detail, dict) else None
    if not isinstance(video, dict):
        return ""
    play_addr = video.get("play_addr")
    if not isinstance(play_addr, dict):
        return ""
    url_list = play_addr.get("url_list")
    if not isinstance(url_list, list):
        return ""
    for url in url_list:
        if isinstance(url, str) and url.startswith("http"):
            return url
    return ""


def _stringify_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_stringify_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "content", "caption", "desc", "sentence"):
            text = _stringify_text(value.get(key))
            if text:
                return text
    return ""


def _guess_doubao_audio_format(media_bytes: bytes) -> str:
    head = media_bytes[:32]
    if head[:4] == b"RIFF" and media_bytes[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if b"ftyp" in head:
        return "m4a"
    return "mp3"


def _guess_media_suffix(media_bytes: bytes) -> str:
    head = media_bytes[:16]
    if head[:4] == b"RIFF" and media_bytes[8:12] == b"WAVE":
        return ".wav"
    if head[:4] == b"FORM" and (media_bytes[8:12] in (b"AIFF", b"AIFC")):
        return ".aiff"
    if head[:4] == b"OggS":
        return ".ogg"
    if head[:4] == b"fLaC":
        return ".flac"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if b"ftyp" in media_bytes[:32]:
        return ".mp4"
    return ".mp4"


def _is_doubao_success(payload: dict[str, Any]) -> bool:
    for key in ("code", "status_code", "status"):
        value = payload.get(key)
        if value is None:
            continue
        if value in (0, "0", 1000, "1000", "success", "Success", "SUCCESS"):
            return True
        return False
    return bool(_extract_doubao_text(payload))


def _extract_doubao_text(payload: dict[str, Any]) -> str:
    for candidate in (
        payload.get("text"),
        payload.get("transcript"),
        _nested(payload, "data", "text"),
        _nested(payload, "result", "text"),
        _nested(payload, "result", "transcript"),
    ):
        text = _stringify_text(candidate)
        if text:
            return text
    for container in (
        _nested(payload, "result", "utterances"),
        _nested(payload, "result", "segments"),
        _nested(payload, "data", "utterances"),
        _nested(payload, "data", "segments"),
    ):
        text = _join_segment_text(container)
        if text:
            return text
    return ""


def _join_segment_text(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value:
        text = _stringify_text(item)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _doubao_error_message(payload: dict[str, Any]) -> str:
    for candidate in (
        payload.get("message"),
        payload.get("msg"),
        payload.get("error"),
        payload.get("errmsg"),
        _nested(payload, "result", "message"),
        _nested(payload, "data", "message"),
    ):
        text = _stringify_text(candidate)
        if text:
            return text
    return "未知错误"


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return message[:200] if isinstance(message, str) else response.text[:200]
