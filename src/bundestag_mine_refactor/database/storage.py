"""Persistence helpers built on SQLAlchemy."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Iterator, Sequence

from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.types import ProtocolMetadata, Speech
from .models import Base, Protocol, SpeechModel


@dataclass(slots=True)
class ProtocolOverview:
    """Lightweight representation of a persisted protocol."""

    identifier: str
    legislative_period: int | None
    session_number: int | None
    date: date | None
    title: str | None
    speech_count: int
    updated_at: datetime | None


class Storage:
    """Wrapper around SQLAlchemy to store protocols and speeches."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ensure_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    def upsert_protocol(self, metadata: ProtocolMetadata) -> Protocol:
        with self.session() as session:
            protocol = session.get(Protocol, metadata.identifier)
            if protocol is None:
                protocol = Protocol(
                    id=metadata.identifier,
                    legislative_period=metadata.legislative_period,
                    session_number=metadata.session_number,
                    date=metadata.date,
                    title=metadata.title,
                )
                session.add(protocol)
                session.flush()
            else:
                protocol.legislative_period = metadata.legislative_period
                protocol.session_number = metadata.session_number
                protocol.date = metadata.date
                protocol.title = metadata.title
            return protocol

    def replace_speeches(self, protocol_id: str, speeches: Sequence[Speech]) -> int:
        with self.session() as session:
            protocol = session.get(Protocol, protocol_id)
            if protocol is None:
                raise ValueError(f"Protocol {protocol_id} must exist before adding speeches")
            session.query(SpeechModel).filter(SpeechModel.protocol_id == protocol_id).delete()
            for speech in speeches:
                speech_model = SpeechModel(
                    protocol_id=protocol_id,
                    sequence_number=speech.sequence_number,
                    speaker_name=speech.speaker_name,
                    party=speech.party,
                    role=speech.role,
                    text=speech.text,
                    summary=speech.summary,
                    sentiment=speech.sentiment,
                    topics=speech.topics,
                )
                session.add(speech_model)
            session.flush()
            return len(speeches)

    def pending_summaries(self, limit: int = 50) -> Iterable[SpeechModel]:
        with self.session() as session:
            stmt = select(SpeechModel).where(SpeechModel.summary.is_(None)).order_by(SpeechModel.id).limit(limit)
            return list(session.scalars(stmt))

    def update_summary(self, speech_id: int, *, summary: str, sentiment: str | None = None, topics: str | None = None) -> None:
        with self.session() as session:
            speech = session.get(SpeechModel, speech_id)
            if speech is None:
                raise ValueError(f"Speech {speech_id} not found")
            speech.summary = summary
            speech.sentiment = sentiment
            speech.topics = topics

    def dispose(self) -> None:
        """Dispose the underlying SQLAlchemy engine."""

        self._engine.dispose()

    def list_protocols(self, limit: int = 25) -> list[ProtocolOverview]:
        """Return a chronological snapshot of the latest stored protocols."""

        with self.session() as session:
            stmt = (
                select(
                    Protocol.id,
                    Protocol.legislative_period,
                    Protocol.session_number,
                    Protocol.date,
                    Protocol.title,
                    Protocol.updated_at,
                    func.count(SpeechModel.id).label("speech_count"),
                )
                .outerjoin(SpeechModel, SpeechModel.protocol_id == Protocol.id)
                .group_by(
                    Protocol.id,
                    Protocol.legislative_period,
                    Protocol.session_number,
                    Protocol.date,
                    Protocol.title,
                    Protocol.updated_at,
                )
                .order_by(
                    Protocol.date.desc().nullslast(),
                    Protocol.updated_at.desc().nullslast(),
                    Protocol.id.desc(),
                )
                .limit(limit)
            )
            rows = session.execute(stmt).all()
            return [
                ProtocolOverview(
                    identifier=row.id,
                    legislative_period=row.legislative_period,
                    session_number=row.session_number,
                    date=row.date,
                    title=row.title,
                    speech_count=row.speech_count or 0,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]


def create_storage(database_url: str, *, echo: bool = False) -> Storage:
    engine = create_engine(database_url, echo=echo, future=True)
    storage = Storage(engine)
    storage.ensure_schema()
    return storage


__all__ = ["ProtocolOverview", "Storage", "create_storage"]
