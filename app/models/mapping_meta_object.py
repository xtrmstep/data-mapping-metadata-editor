from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mapping_meta_entry import MappingMetaEntry


class MappingMetaObject(Base):
    """Meta-level link between a destination meta object and a source meta object.

    A 'meta object' groups physical tables/topics that share the same logical
    identity (same database + table_name for destinations; same
    db.schema.table or topic for sources) across different clusters and servers.

    destination_meta_name -- natural key derived as ``"{database}.{table_name}"``
    source_meta_name      -- ``"{database}.{schema}.{table_name}"`` for postgres
                             or ``"kafka:{topic}"`` for kafka
    """

    __tablename__ = "mapping_meta_object"
    __table_args__ = (
        UniqueConstraint(
            "destination_meta_name",
            "source_meta_name",
            name="uq_meta_object_dst_src",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    destination_meta_name: Mapped[str] = mapped_column(String, nullable=False)

    source_meta_name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)  # "postgres" | "kafka"

    # JSON list of {"name": str, "type": str, "nullable": bool, "description": str|None}
    destination_schema_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    source_schema_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    entries: Mapped[list[MappingMetaEntry]] = relationship(
        back_populates="meta_object", cascade="all, delete-orphan"
    )
