"""One persistence model; SQLAlchemy NUMERIC keeps money exact on PostgreSQL."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    filename: Mapped[str] = mapped_column(String(250))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    uploader: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String(60))
    pages: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(40), default="RECEIVED", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    candidate: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attempt(Base):
    __tablename__ = "extraction_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    route: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    candidate: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Issue(Base):
    __tablename__ = "validation_issues"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(30))
    field: Mapped[str] = mapped_column(String(80))
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(250), nullable=True)
    vendor_normalized: Mapped[str] = mapped_column(String(250), index=True)
    document_number: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    total: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(3), index=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(80))
    operation: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    safe_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Usage(Base):
    __tablename__ = "llm_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(50))
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Content(Base):
    __tablename__ = "content_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Revision(Base):
    __tablename__ = "content_revisions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("content_items.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    drafts: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    channels: Mapped[list] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[str] = mapped_column(String(150), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("content_revisions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Delivery(Base):
    __tablename__ = "integration_deliveries"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    expense_id: Mapped[str] = mapped_column(ForeignKey("expenses.id"), unique=True)
    row_number: Mapped[int] = mapped_column(Integer, unique=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Idempotency(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
