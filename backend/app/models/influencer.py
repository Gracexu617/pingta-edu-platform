from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InfluencerModel(Base):
    __tablename__ = "influencers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    core_views: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    style_traits: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    common_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parent_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    content_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class InfluencerContentModel(Base):
    __tablename__ = "influencer_contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    influencer_id: Mapped[int] = mapped_column(ForeignKey("influencers.id"), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
