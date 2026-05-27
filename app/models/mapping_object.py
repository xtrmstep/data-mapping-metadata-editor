from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.destination import Destination
    from app.models.mapping_field import MappingField
    from app.models.source import Source


class MappingObject(Base):
    """Object-level link between a source and a destination."""

    __tablename__ = "mapping_object"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"), nullable=False)
    destination_id: Mapped[int] = mapped_column(ForeignKey("destination.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="mapping_objects")
    destination: Mapped[Destination] = relationship(back_populates="mapping_objects")
    fields: Mapped[list[MappingField]] = relationship(
        back_populates="mapping_object", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "destination_id", name="uq_mapping_object_src_dst"),
    )
