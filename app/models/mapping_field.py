from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.mapping_object import MappingObject


class MappingField(Base):
    """Field-level mapping within a MappingObject."""

    __tablename__ = "mapping_field"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mapping_object_id: Mapped[int] = mapped_column(
        ForeignKey("mapping_object.id"), nullable=False
    )
    source_field: Mapped[str] = mapped_column(String, nullable=False)
    source_field_type: Mapped[str | None] = mapped_column(String, nullable=True)
    destination_field: Mapped[str | None] = mapped_column(String, nullable=True)
    destination_field_type: Mapped[str | None] = mapped_column(String, nullable=True)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)

    mapping_object: Mapped[MappingObject] = relationship(back_populates="fields")

    __table_args__ = (
        UniqueConstraint(
            "mapping_object_id", "destination_field", name="uq_mapping_field_obj_dst"
        ),
    )
