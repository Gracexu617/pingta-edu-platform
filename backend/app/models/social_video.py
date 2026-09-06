from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SocialVideoModel(Base):
    __tablename__ = "social_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(240), index=True, nullable=False)
    creator: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(24), nullable=False)
    scope: Mapped[str] = mapped_column(String(24), nullable=False)
    original_url: Mapped[str] = mapped_column(String(800), nullable=False)
    play_url: Mapped[str] = mapped_column(String(800), nullable=False, default="")
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold: Mapped[str] = mapped_column(String(80), nullable=False)
    is_hot: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript_source: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    transcript_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manuscript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
