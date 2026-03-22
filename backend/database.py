"""Database configuration and SQLAlchemy models for the MVP.

This module defines the relational schema for a simple customer support system.
It uses SQLAlchemy 2.0 style typing and is designed for PostgreSQL.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from enum import Enum
from typing import Generator

from sqlalchemy import DateTime, ForeignKey, String, create_engine, func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def _build_database_url() -> str:
    """Return the database URL from env.

    Priority:
    1) DATABASE_URL
    2) POSTGRES_* pieces

    Defaults are chosen for local development.
    """

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    user = os.getenv("POSTGRES_USER", "admin")
    password = os.getenv("POSTGRES_PASSWORD", "password123")
    db = os.getenv("POSTGRES_DB", "support_db")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


DATABASE_URL = _build_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class SenderType(str, Enum):
    """Allowed message sender types."""

    customer = "customer"
    agent = "agent"


class Agent(Base):
    """Support agent."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)

    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="agent",
        cascade="save-update",
    )


class MockCustomer(Base):
    """Mock customer table used for MVP demo purposes."""

    __tablename__ = "mock_customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    subscription_plan: Mapped[str] = mapped_column(String(50), nullable=False)

    tickets: Mapped[list[Ticket]] = relationship(back_populates="customer")


class Ticket(Base):
    """Support ticket."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)

    customer_email: Mapped[str] = mapped_column(
        String(320), ForeignKey("mock_customers.email"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'open'")
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_draft: Mapped[str | None] = mapped_column(nullable=True)

    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    customer: Mapped[MockCustomer] = relationship(back_populates="tickets")
    agent: Mapped[Agent | None] = relationship(back_populates="tickets")
    messages: Mapped[list[Message]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    @property
    def suggested_agent_id(self) -> int | None:
        """Return the suggested agent for this ticket.

        This is computed from the category so it remains stable even if the
        ticket is manually reassigned.
        """

        category = (self.category or "").lower().strip()
        if category == "bug":
            return 1
        if category == "refund":
            return 2
        if category:
            return 3
        return None


class Message(Base):
    """Message within a ticket conversation."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)

    sender_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'customer'")
    )

    body: Mapped[str] = mapped_column(nullable=False)
    outlook_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ticket: Mapped[Ticket] = relationship(back_populates="messages")


def init_db() -> None:
    """Create database tables.

    In containerized environments Postgres may take a few seconds to accept
    connections. This function retries before failing.
    """

    wait_for_db()
    Base.metadata.create_all(bind=engine)


def wait_for_db(max_attempts: int = 30, initial_delay_s: float = 0.5) -> None:
    """Wait until the database accepts connections.

    Raises:
        OperationalError: if the DB is still unreachable after the retries.
    """

    delay_s = initial_delay_s
    last_error: OperationalError | None = None

    for _ in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(delay_s)
            delay_s = min(delay_s * 1.5, 5.0)

    assert last_error is not None
    raise last_error


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session."""

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
