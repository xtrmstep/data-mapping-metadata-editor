from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mapping_object import MappingObject
    from app.models.source_schema import SourceSchema


class Source(Base):
    """A source system object — either a PostgreSQL table or a Kafka topic."""

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # "postgres" | "kafka"

    # Shared — Kafka cluster name or point of presence for database servers
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # PostgreSQL-specific
    server: Mapped[str | None] = mapped_column(String, nullable=True)
    database: Mapped[str | None] = mapped_column(String, nullable=True)
    pg_schema: Mapped[str | None] = mapped_column(String, nullable=True)
    table_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Kafka-specific
    kafka: Mapped[str | None] = mapped_column(String, nullable=True)
    brokers: Mapped[str | None] = mapped_column(String, nullable=True)
    topic: Mapped[str | None] = mapped_column(String, nullable=True)

    def identity_clauses(self) -> list:
        """Return SQLAlchemy filter conditions that uniquely identify this source."""
        if self.source_type == "kafka":
            return [
                Source.source_type == "kafka",
                Source.cluster_name == self.cluster_name,
                Source.topic == self.topic
            ]
        if self.source_type == "postgres":
            return [
                Source.source_type == self.source_type,
                Source.server == self.server,
                Source.database == self.database,
                Source.pg_schema == self.pg_schema,
                Source.table_name == self.table_name,
            ]
        # not supported source type - throw an error
        raise ValueError(f"Unsupported source type: {self.source_type}")

    schema_fields: Mapped[list[SourceSchema]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    mapping_objects: Mapped[list[MappingObject]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
