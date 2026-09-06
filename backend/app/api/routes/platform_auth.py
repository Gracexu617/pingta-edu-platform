from fastapi import APIRouter, Request

from app.schemas.platform_auth import PlatformAuthStatusResponse, ProviderAuthStatus

router = APIRouter(prefix="/api/v1/platform-auth", tags=["platform-auth"])


@router.get("/status", response_model=PlatformAuthStatusResponse)
async def platform_auth_status(request: Request) -> PlatformAuthStatusResponse:
    settings = request.app.state.settings
    douyin_configured = bool(settings.douyin_client_key and settings.douyin_client_secret)
    wechat_configured = bool(
        settings.wechat_channels_app_id and settings.wechat_channels_app_secret
    )
    video_data_configured = (
        settings.video_data_provider == "tikhub" and bool(settings.tikhub_api_key)
    )
    return PlatformAuthStatusResponse(
        providers=[
            ProviderAuthStatus(
                provider="抖音",
                configured=douyin_configured,
                oauth_ready=douyin_configured,
                note="配置抖音开放平台应用后可接 OAuth 和视频数据接口。",
            ),
            ProviderAuthStatus(
                provider="微信视频号",
                configured=wechat_configured,
                oauth_ready=False,
                note="视频号需账号授权或第三方数据源，当前先预留配置。",
            ),
            ProviderAuthStatus(
                provider="全网热门视频数据源",
                configured=video_data_configured,
                oauth_ready=video_data_configured,
                note="配置 TikHub/第三方数据 API 后，只推送带真实点赞收藏且达标的视频。",
            ),
        ]
    )
