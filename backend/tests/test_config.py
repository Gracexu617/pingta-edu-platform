from app.core.config import Settings


def test_social_video_auto_collect_interval_defaults_to_ten_minutes() -> None:
    assert Settings().social_video_auto_collect_interval_seconds == 600
