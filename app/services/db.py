from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect as sa_inspect, select, distinct
from sqlalchemy.orm import Session, sessionmaker, selectinload

from app.models.orm import (
    Base,
    Destination,
    DestinationSchema,
    MappingField,
    MappingMetaEntry,
    MappingMetaObject,
    MappingObject,
    Source,
    SourceSchema,
)

_engine = None
_SessionFactory = None


def _get_engine():
    global _engine, _SessionFactory
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        _engine = create_engine(url)
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def _session() -> Generator[Session, None, None]:
    _get_engine()
    s: Session = _SessionFactory()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _merge_fields(target, source) -> None:
    """Copy all non-PK mapped column values from source onto target."""
    mapper = sa_inspect(type(source)).mapper
    for col_attr in mapper.column_attrs:
        if col_attr.key == "id":
            continue
        setattr(target, col_attr.key, getattr(source, col_attr.key))



# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


def save_source(source: Source) -> int:
    """Persist a source, inserting or updating by its natural key."""
    with _session() as s:
        existing = s.scalar(select(Source).where(*source.identity_clauses()))
        if existing is None:
            s.add(source)
            obj = source
        else:
            _merge_fields(existing, source)
            obj = existing
        s.flush()
        return obj.id


def delete_source(source: Source) -> None:
    """Delete a persisted source matched by its natural key."""
    with _session() as s:
        obj = s.scalar(select(Source).where(*source.identity_clauses()))
        if obj is not None:
            s.delete(obj)


def list_source_types() -> list[str]:
    with _session() as s:
        rows = s.scalars(select(distinct(Source.source_type)).order_by(Source.source_type)).all()
        return list(rows)


def list_cluster_names(source_type: str | None = None) -> list[str]:
    with _session() as s:
        q = select(distinct(Source.cluster_name)).order_by(Source.cluster_name)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_server_names(
    source_type: str | None = None,
    cluster_name: str | None = None,
) -> list[str]:
    with _session() as s:
        q = select(distinct(Source.server)).order_by(Source.server)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        if cluster_name is not None:
            q = q.where(Source.cluster_name == cluster_name)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_database_names(
    source_type: str | None = None,
    cluster_name: str | None = None,
    server: str | None = None,
) -> list[str]:
    with _session() as s:
        q = select(distinct(Source.database)).order_by(Source.database)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        if cluster_name is not None:
            q = q.where(Source.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Source.server == server)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_schema_names(
    source_type: str | None = None,
    cluster_name: str | None = None,
    server: str | None = None,
    database: str | None = None,
) -> list[str]:
    with _session() as s:
        q = select(distinct(Source.pg_schema)).order_by(Source.pg_schema)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        if cluster_name is not None:
            q = q.where(Source.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Source.server == server)
        if database is not None:
            q = q.where(Source.database == database)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_table_names(
    source_type: str | None = None,
    cluster_name: str | None = None,
    server: str | None = None,
    database: str | None = None,
    pg_schema: str | None = None,
) -> list[str]:
    with _session() as s:
        q = select(distinct(Source.table_name)).order_by(Source.table_name)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        if cluster_name is not None:
            q = q.where(Source.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Source.server == server)
        if database is not None:
            q = q.where(Source.database == database)
        if pg_schema is not None:
            q = q.where(Source.pg_schema == pg_schema)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_sources(
    source_type: str | None = None,
    cluster_name: str | None = None,
    server: str | None = None,
    database: str | None = None,
    pg_schema: str | None = None,
    table_name: str | None = None,
) -> list[Source]:
    with _session() as s:
        q = select(Source).options(selectinload(Source.schema_fields)).order_by(Source.id)
        if source_type is not None:
            q = q.where(Source.source_type == source_type)
        if cluster_name is not None:
            q = q.where(Source.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Source.server == server)
        if database is not None:
            q = q.where(Source.database == database)
        if pg_schema is not None:
            q = q.where(Source.pg_schema == pg_schema)
        if table_name is not None:
            q = q.where(Source.table_name == table_name)
        return s.scalars(q).all()


def update_source_schema(
    source_id: int, fields: list[dict]
) -> None:
    with _session() as s:
        src = s.scalar(
            select(Source)
            .options(selectinload(Source.schema_fields))
            .where(Source.id == source_id)
        )
        if src is None:
            return
        for sf in list(src.schema_fields):
            s.delete(sf)
        s.flush()
        for f in fields:
            s.add(
                SourceSchema(
                    source_id=src.id,
                    field_name=str(f.get("name") or ""),
                    field_type=str(f.get("type") or "string"),
                    nullable=bool(f.get("nullable", True)),
                    description=f.get("description") or None,
                )
            )


# ---------------------------------------------------------------------------
# Destination
# ---------------------------------------------------------------------------


def save_destination(destination: Destination) -> int:
    """Persist a destination, inserting or updating by its natural key."""
    with _session() as s:
        existing = s.scalar(select(Destination).where(*destination.identity_clauses()))
        if existing is None:
            s.add(destination)
            obj = destination
        else:
            _merge_fields(existing, destination)
            obj = existing
        s.flush()
        return obj.id


def delete_destination(destination: Destination) -> None:
    """Delete a persisted destination matched by its natural key."""
    with _session() as s:
        obj = s.scalar(select(Destination).where(*destination.identity_clauses()))
        if obj is not None:
            s.delete(obj)


def list_destination_cluster_names() -> list[str]:
    with _session() as s:
        rows = s.scalars(select(distinct(Destination.cluster_name)).order_by(Destination.cluster_name)).all()
        return [r for r in rows if r is not None]


def list_destination_server_names(cluster_name: str | None = None) -> list[str]:
    with _session() as s:
        q = select(distinct(Destination.server)).order_by(Destination.server)
        if cluster_name is not None:
            q = q.where(Destination.cluster_name == cluster_name)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_destination_table_names(cluster_name: str | None = None, server: str | None = None) -> list[str]:
    with _session() as s:
        q = select(distinct(Destination.table_name)).order_by(Destination.table_name)
        if cluster_name is not None:
            q = q.where(Destination.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Destination.server == server)
        rows = s.scalars(q).all()
        return [r for r in rows if r is not None]


def list_destinations(
    cluster_name: str | None = None,
    server: str | None = None,
    table_name: str | None = None,
) -> list[Destination]:
    with _session() as s:
        q = (
            select(Destination)
            .options(selectinload(Destination.schema_fields))
            .order_by(Destination.table_name)
        )
        if cluster_name is not None:
            q = q.where(Destination.cluster_name == cluster_name)
        if server is not None:
            q = q.where(Destination.server == server)
        if table_name is not None:
            q = q.where(Destination.table_name == table_name)
        return s.scalars(q).all()


def update_destination_schema(destination_id: int, fields: list[dict]) -> None:
    with _session() as s:
        dst = s.scalar(
            select(Destination)
            .options(selectinload(Destination.schema_fields))
            .where(Destination.id == destination_id)
        )
        if dst is None:
            return
        for sf in list(dst.schema_fields):
            s.delete(sf)
        s.flush()
        for f in fields:
            s.add(
                DestinationSchema(
                    destination_id=dst.id,
                    field_name=str(f.get("name") or ""),
                    field_type=str(f.get("type") or "String"),
                    nullable=bool(f.get("nullable", True)),
                    description=f.get("description") or None,
                )
            )


# ---------------------------------------------------------------------------
# MappingObject
# ---------------------------------------------------------------------------


def upsert_mapping_object(source_id: int, destination_id: int) -> int:
    with _session() as s:
        existing = s.scalar(
            select(MappingObject).where(
                MappingObject.source_id == source_id,
                MappingObject.destination_id == destination_id,
            )
        )
        if existing is None:
            existing = MappingObject(source_id=source_id, destination_id=destination_id)
            s.add(existing)
            s.flush()
        return existing.id


def list_mapping_objects() -> list[MappingObject]:
    with _session() as s:
        return s.scalars(
            select(MappingObject).options(
                selectinload(MappingObject.source),
                selectinload(MappingObject.destination),
                selectinload(MappingObject.fields),
            )
        ).all()


# ---------------------------------------------------------------------------
# MappingField
# ---------------------------------------------------------------------------


def save_mapping_field(
    mapping_object_id: int,
    destination_field: str,
    *,
    source_field: str,
    source_field_type: str = "",
    destination_field_type: str = "",
    expression: str = "",
) -> None:
    """Persist a single field mapping, inserting or updating by (mapping_object_id, destination_field)."""
    with _session() as s:
        mf = s.scalar(
            select(MappingField).where(
                MappingField.mapping_object_id == mapping_object_id,
                MappingField.destination_field == (destination_field or None),
            )
        )
        if mf is None:
            mf = MappingField(mapping_object_id=mapping_object_id)
            s.add(mf)
        mf.source_field = source_field
        mf.source_field_type = source_field_type or None
        mf.destination_field = destination_field or None
        mf.destination_field_type = destination_field_type or None
        mf.expression = expression or None


def delete_mapping_fields(mapping_object_id: int) -> None:
    """Delete all field mappings for a mapping object."""
    with _session() as s:
        mfs = s.scalars(
            select(MappingField).where(MappingField.mapping_object_id == mapping_object_id)
        ).all()
        for mf in mfs:
            s.delete(mf)


def delete_mapping_field(mapping_object_id: int, source_field: str) -> None:
    """Delete a single field mapping by source field name."""
    with _session() as s:
        mf = s.scalar(
            select(MappingField).where(
                MappingField.mapping_object_id == mapping_object_id,
                MappingField.source_field == source_field,
            )
        )
        if mf is not None:
            s.delete(mf)


# ---------------------------------------------------------------------------
# MappingMetaObject helpers
# ---------------------------------------------------------------------------


def _destination_meta_name(dst: Destination) -> str:
    """Derive the meta name that groups same-schema destination tables across clusters/servers."""
    parts = [p for p in (dst.database, dst.table_name) if p]
    return ".".join(parts) if parts else str(dst.id)


def _source_meta_name(src: Source) -> str:
    """Derive the meta name that groups same-schema source objects across clusters/servers."""
    if src.source_type == "kafka":
        return f"kafka:{src.topic or src.id}"
    # postgres
    parts = [p for p in (src.database, src.pg_schema, src.table_name) if p]
    return ".".join(parts) if parts else str(src.id)


# ---------------------------------------------------------------------------
# MappingMetaObject
# ---------------------------------------------------------------------------


def rebuild_meta_objects() -> int:
    """Drop all MappingMetaObject rows and recreate from existing MappingObjects.

    Returns the number of meta objects created.
    """
    with _session() as s:
        # Clear existing meta objects (cascade deletes entries)
        existing = s.scalars(select(MappingMetaObject)).all()
        for obj in existing:
            s.delete(obj)
        s.flush()

        # Reload MappingObjects with their source/destination relationships
        mos = s.scalars(
            select(MappingObject).options(
                selectinload(MappingObject.source),
                selectinload(MappingObject.destination),
            )
        ).all()

        seen: dict[tuple[str, str], MappingMetaObject] = {}
        for mo in mos:
            dst_name = _destination_meta_name(mo.destination)
            src_name = _source_meta_name(mo.source)
            key = (dst_name, src_name)
            if key not in seen:
                meta = MappingMetaObject(
                    destination_meta_name=dst_name,
                    source_meta_name=src_name,
                    source_type=mo.source.source_type,
                )
                s.add(meta)
                seen[key] = meta

        s.flush()
        return len(seen)


def list_meta_objects() -> list[MappingMetaObject]:
    with _session() as s:
        return s.scalars(
            select(MappingMetaObject)
            .options(selectinload(MappingMetaObject.entries))
            .order_by(MappingMetaObject.destination_meta_name, MappingMetaObject.source_meta_name)
        ).all()


def update_meta_destination_schema(destination_meta_name: str, fields: list[dict]) -> int:
    """Set destination_schema_json on every meta object with this destination name.

    Returns the number of rows updated.
    """
    with _session() as s:
        rows = s.scalars(
            select(MappingMetaObject).where(
                MappingMetaObject.destination_meta_name == destination_meta_name
            )
        ).all()
        for row in rows:
            row.destination_schema_json = fields
        return len(rows)


def update_meta_source_schema(source_meta_name: str, fields: list[dict]) -> int:
    """Set source_schema_json on every meta object with this source name.

    Returns the number of rows updated.
    """
    with _session() as s:
        rows = s.scalars(
            select(MappingMetaObject).where(
                MappingMetaObject.source_meta_name == source_meta_name
            )
        ).all()
        for row in rows:
            row.source_schema_json = fields
        return len(rows)


# ---------------------------------------------------------------------------
# MappingMetaEntry
# ---------------------------------------------------------------------------


def save_meta_entry(
    meta_object_id: int,
    destination_field: str,
    *,
    source_field: str,
    expression: str = "",
) -> None:
    """Persist a single meta field mapping, inserting or updating by (meta_object_id, destination_field)."""
    with _session() as s:
        entry = s.scalar(
            select(MappingMetaEntry).where(
                MappingMetaEntry.meta_object_id == meta_object_id,
                MappingMetaEntry.destination_field == destination_field,
            )
        )
        if entry is None:
            entry = MappingMetaEntry(
                meta_object_id=meta_object_id,
                destination_field=destination_field,
            )
            s.add(entry)
        entry.source_field = source_field or None
        entry.expression = expression or None


def delete_meta_entries(meta_object_id: int) -> None:
    """Delete all meta field mappings for a meta object."""
    with _session() as s:
        entries = s.scalars(
            select(MappingMetaEntry).where(MappingMetaEntry.meta_object_id == meta_object_id)
        ).all()
        for e in entries:
            s.delete(e)

