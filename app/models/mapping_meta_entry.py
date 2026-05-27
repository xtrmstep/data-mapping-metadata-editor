from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mapping_meta_object import MappingMetaObject


class MappingMetaEntry(Base):
    """Field-level mapping within a MappingMetaObject."""

    __tablename__ = "mapping_meta_entry"
    __table_args__ = (
        UniqueConstraint(
            "meta_object_id",
            "destination_field",
            name="uq_meta_entry_obj_dst",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meta_object_id: Mapped[int] = mapped_column(
        ForeignKey("mapping_meta_object.id"), nullable=False
    )
    destination_field: Mapped[str] = mapped_column(String, nullable=False)
    source_field: Mapped[str | None] = mapped_column(String, nullable=True)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta_object: Mapped[MappingMetaObject] = relationship(back_populates="entries")
