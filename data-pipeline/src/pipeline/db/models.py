from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Index

from sqlalchemy import (
    BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="source")

class Factor(Base):
    __tablename__ = "factors"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    source_hint: Mapped[str | None] = mapped_column(String(64))

class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_type: Mapped[str | None] = mapped_column(String(32))
    schema_version: Mapped[str | None] = mapped_column(String(32))

    source: Mapped[Source] = relationship(back_populates="datasets")
    files: Mapped[list["FileRecord"]] = relationship(back_populates="dataset")


class FileRecord(Base):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("url", "checksum_sha256", name="uq_url_checksum"),
        Index("ix_files_dataset_year", "dataset_id", "year"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    period: Mapped[str | None] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(128))
    year: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    superseded_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("files.id")
    )
    bronze_path: Mapped[str | None] = mapped_column(Text)
    silver_path: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="files")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    file_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("files.id")
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    pipeline_version: Mapped[str | None] = mapped_column(String(32))

class FactorSource(Base):
    """Связь фактора с источником данных.

    Композитный PK: (factor_code, source_id). Один фактор может иметь
    несколько источников (например, ЕМИСС + верификация из РПН).
    """

    __tablename__ = "factor_sources"

    factor_code: Mapped[str] = mapped_column(
        ForeignKey("factors.code", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)
    filter_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    match_method: Mapped[str] = mapped_column(String(32), default="auto", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)