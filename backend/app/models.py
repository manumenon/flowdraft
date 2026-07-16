import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

def utc_now() -> datetime:
    """Helper to return the current time in UTC with timezone info."""
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    diagrams: Mapped[List["Diagram"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    export_jobs: Mapped[List["ExportJob"]] = relationship(
        back_populates="user"
    )


class Diagram(Base):
    __tablename__ = "diagrams"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(
        String, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    spec: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )
    theme: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="diagrams"
    )
    export_jobs: Mapped[List["ExportJob"]] = relationship(
        back_populates="diagram", cascade="all, delete-orphan"
    )

    @property
    def diagram_id(self) -> uuid.UUID:
        return self.id


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    diagram_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("diagrams.id", ondelete="SET NULL"), nullable=True
    )
    spec_override: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    format: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "mp4" or "gif"
    status: Mapped[str] = mapped_column(
        String, default="queued", nullable=False
    )  # "queued", "processing", "completed", "failed"
    error_message: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    download_url: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    diagram: Mapped[Optional["Diagram"]] = relationship(
        back_populates="export_jobs"
    )
    user: Mapped[Optional["User"]] = relationship(
        back_populates="export_jobs"
    )
