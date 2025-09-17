"""SQLAlchemy models for the refactored Bundestags-Mine pipeline."""
from __future__ import annotations

from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative SQLAlchemy base class."""


class Protocol(Base):
    """Database representation of a plenary protocol."""

    __tablename__ = "protocols"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    legislative_period: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    speeches: Mapped[List["SpeechModel"]] = relationship(
        back_populates="protocol", cascade="all, delete-orphan"
    )


class SpeechModel(Base):
    """Database representation of a speech."""

    __tablename__ = "speeches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    protocol_id: Mapped[str] = mapped_column(String(128), ForeignKey("protocols.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, index=True)
    speaker_name: Mapped[str] = mapped_column(String(256))
    party: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    topics: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    protocol: Mapped[Protocol] = relationship(back_populates="speeches")


__all__ = ["Base", "Protocol", "SpeechModel"]
