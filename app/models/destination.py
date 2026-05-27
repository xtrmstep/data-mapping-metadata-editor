from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.destination_schema import DestinationSchema
    from app.models.mapping_object import MappingObject


class Destination(Base):
    """A destination ClickHouse table."""

    __tablename__ = "destination"
    __table_args__ = (UniqueConstraint("cluster_name", "server", "database", "table_name", name="uq_destination_natural_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    cluster_name: Mapped[str | None] = mapped_column(String, nullable=True)
    server: Mapped[str | None] = mapped_column(String, nullable=True)
    database: Mapped[str | None] = mapped_column(String, nullable=True)

    def identity_clauses(self) -> list:
        """Return SQLAlchemy filter conditions that uniquely identify this destination."""
        return [
            Destination.cluster_name == self.cluster_name,
            Destination.server == self.server,
            Destination.database == self.database,
            Destination.table_name == self.table_name,
        ]

    schema_fields: Mapped[list[DestinationSchema]] = relationship(
        back_populates="destination", cascade="all, delete-orphan"
    )
    mapping_objects: Mapped[list[MappingObject]] = relationship(
        back_populates="destination", cascade="all, delete-orphan"
    )
