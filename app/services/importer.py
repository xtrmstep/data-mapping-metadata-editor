from typing import Any, Protocol

import pandas as pd

from app.models.orm import Source, Destination
from .db import (
    save_destination,
    save_source,
    delete_source,
    delete_destination,
    upsert_mapping_object,
)
from .validators import validate_import_row


class SourceImportStrategy(Protocol):
    def source_key(self, row: dict[str, Any]) -> str:
        """Returns the source import key for a validated row."""

    def create_source(self, row: dict[str, Any]) -> tuple[str, Source]:
        """Creates a source import key and ORM object from a validated row."""

    def delete_source(self, source: Source) -> None:
        """Deletes an existing persisted source matching the import source."""

    def upsert_source(self, source: Source) -> int:
        """Persists the source and returns its ID."""


class KafkaSourceImportStrategy:
    def source_key(self, row: dict[str, Any]) -> str:
        cluster = str(row["cluster_name"]).strip()
        topic = str(row["source_kafka_topic"]).strip()
        return f"kafka:{cluster}:{topic}"

    def create_source(self, row: dict[str, Any]) -> tuple[str, Source]:
        topic = str(row["source_kafka_topic"]).strip()
        return self.source_key(row), Source(
            source_type="kafka",
            cluster_name=str(row["cluster_name"]).strip() or None,
            kafka=str(row.get("source_kafka") or "").strip() or None,
            brokers=str(row["source_kafka_brokers"]).strip() or None,
            topic=topic,
        )

    def delete_source(self, source: Source) -> None:
        delete_source(source)

    def upsert_source(self, source: Source) -> int:
        return save_source(source)


class PostgresSourceImportStrategy:
    def source_key(self, row: dict[str, Any]) -> str:
        server = str(row["source_server"]).strip()
        database = str(row["source_database"]).strip()
        pg_schema = str(row["source_schema"]).strip()
        table_name = str(row["source_table"]).strip()
        return f"{server}:{database}:{pg_schema}:{table_name}"

    def create_source(self, row: dict[str, Any]) -> tuple[str, Source]:
        cluster_name = str(row["cluster_name"]).strip()
        server = str(row["source_server"]).strip()
        database = str(row["source_database"]).strip()
        pg_schema = str(row["source_schema"]).strip()
        table_name = str(row["source_table"]).strip()
        return self.source_key(row), Source(
            source_type="postgres",
            cluster_name=cluster_name,
            server=server,
            database=database,
            pg_schema=pg_schema,
            table_name=table_name,
        )

    def delete_source(self, source: Source) -> None:
        delete_source(source)

    def upsert_source(self, source: Source) -> int:
        return save_source(source)


def insert_mapping_objects(
    valid_rows: list[dict[str, Any]],
    source_id_map: dict[str, int],
    destination_id_map: dict[tuple, int],
    source_strategy: SourceImportStrategy,
) -> tuple[int, int]:
    """Creates mapping objects between sources and destinations.

    Returns:
        (mappings_count, multi_source_destinations_count) where
        multi_source_destinations_count is the number of destinations
        that have more than one distinct source mapped to them.
    """
    created_mappings: set[tuple[int, int]] = set()
    for row_dict in valid_rows:
        source_key = source_strategy.source_key(row_dict)
        dest_key, _ = create_destination(row_dict)
        source_id = source_id_map[source_key]
        destination_id = destination_id_map[dest_key]
        if (source_id, destination_id) not in created_mappings:
            upsert_mapping_object(source_id, destination_id)
            created_mappings.add((source_id, destination_id))

    dest_sources: dict[int, set[int]] = {}
    for source_id, destination_id in created_mappings:
        dest_sources.setdefault(destination_id, set()).add(source_id)
    multi_source_destinations = sum(1 for sources in dest_sources.values() if len(sources) > 1)

    return len(created_mappings), multi_source_destinations


def insert_sources_and_destinations(
    sources: dict[str, Source],
    destinations: dict[tuple, Destination],
    source_strategy: SourceImportStrategy,
) -> tuple[dict[str, int], dict[tuple, int], dict[str, int]]:
    """Inserts sources and destinations and returns their ID maps plus insertion counts."""
    source_id_map: dict[str, int] = {}
    for source_key, source_obj in sources.items():
        source_id_map[source_key] = source_strategy.upsert_source(source_obj)

    destination_id_map: dict[tuple, int] = {}
    for dest_key, dest_obj in destinations.items():
        destination_id_map[dest_key] = save_destination(dest_obj)

    counts = {"sources": len(source_id_map), "destinations": len(destination_id_map)}
    return source_id_map, destination_id_map, counts


def delete_sources_and_destinations(
    sources: dict[str, Source],
    destinations: dict[tuple, Destination],
    source_strategy: SourceImportStrategy,
) -> None:
    """Deletes all persisted sources and destinations matching the imported sets."""
    for source_obj in sources.values():
        source_strategy.delete_source(source_obj)
    for dest_obj in destinations.values():
        delete_destination(dest_obj)


def create_destination(row: dict[str, Any]) -> tuple[tuple[str | None, str | None, str | None, str], Destination]:
    """Creates a destination natural key and ORM object from a validated row.

    The destination cluster is shared with the source — both belong to the same cluster.
    """
    dest_cluster = str(row.get("cluster_name") or "").strip() or None
    dest_server = str(row.get("destination_server") or "").strip() or None
    dest_database = str(row.get("destination_database") or "").strip() or None
    dest_table = str(row["destination_table"]).strip()
    dest_key = (dest_cluster, dest_server, dest_database, dest_table)
    return dest_key, Destination(cluster_name=dest_cluster, table_name=dest_table, server=dest_server, database=dest_database)


SOURCE_IMPORT_STRATEGIES: dict[str, SourceImportStrategy] = {
    "kafka": KafkaSourceImportStrategy(),
    "postgres": PostgresSourceImportStrategy(),
}


def get_source_import_strategy(source_type: str) -> SourceImportStrategy | None:
    return SOURCE_IMPORT_STRATEGIES.get(source_type.strip().lower())


def normalize_import_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Strips column-name whitespace and fills NaN with empty strings."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out.fillna("")


def validate_import_dataframe(df: pd.DataFrame, source_type: str) -> dict:
    """Validates import rows and returns valid rows plus error details."""
    expected_source_type = source_type.strip().lower()
    row_errors = []
    valid_rows = []

    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        row_source_type = str(row_dict.get("source_type") or "").strip().lower()
        errors = []

        if row_source_type != expected_source_type:
            errors.append(f"source_type must be '{expected_source_type}' for selected import type")
        else:
            errors.extend(validate_import_row(row_dict, expected_source_type))

        if errors:
            row_errors.append(f"row {idx + 2}: " + "; ".join(errors))
        else:
            valid_rows.append(row_dict)

    if row_errors:
        return {"ok": False, "errors": row_errors, "valid_rows": valid_rows}

    return {"ok": True, "errors": [], "valid_rows": valid_rows}


def import_sources_and_destinations(df: pd.DataFrame, source_type: str) -> dict:
    """
    Imports sources and destinations from a CSV DataFrame.
    
    Logic:
    1. Normalize the dataframe
    2. Validate all rows; stop if any validation fails
    3. Accumulate unique Source and Destination objects from all rows
    4. Delete all existing sources and destinations that match the imported set
    5. Insert new source and destination records along with mapping objects
    """
    # Step 1: Normalize the dataframe
    df = normalize_import_dataframe(df)

    # Step 2: Validate all rows before importing
    validation_result = validate_import_dataframe(df, source_type)
    if not validation_result["ok"]:
        return validation_result

    source_strategy = get_source_import_strategy(source_type)
    if not source_strategy:
        return {"ok": False, "errors": [f"Unsupported source type: {source_type}"], "valid_rows": []}

    # Step 3: Accumulate unique sources and destinations
    sources_to_import: dict[str, Source] = {}  # Natural key -> Source object
    destinations_to_import: dict[str, Destination] = {}  # table_name -> Destination object

    for row_dict in validation_result["valid_rows"]:
        source_key, source = source_strategy.create_source(row_dict)
        if source_key not in sources_to_import:
            sources_to_import[source_key] = source

        # Create Destination object
        dest_key, destination = create_destination(row_dict)
        if dest_key not in destinations_to_import:
            destinations_to_import[dest_key] = destination

    # Step 4: Delete all existing sources and destinations in the import set
    delete_sources_and_destinations(sources_to_import, destinations_to_import, source_strategy)

    # Step 5: Insert new sources, destinations, and mapping objects
    source_id_map, destination_id_map, counts = insert_sources_and_destinations(sources_to_import, destinations_to_import, source_strategy)

    # Second pass: create mapping objects between sources and destinations
    mappings_count, multi_source_destinations = insert_mapping_objects(
        validation_result["valid_rows"], source_id_map, destination_id_map, source_strategy
    )

    return {
        "ok": True,
        "total_records": mappings_count,
        "total_sources": counts["sources"],
        "total_destinations": counts["destinations"],
        "multi_source_destinations": multi_source_destinations,
    }



def json_schema_to_fields(schema: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    """Flattens a JSON Schema into a list of scalar leaf field descriptors with dot-notation paths."""
    stype = schema.get("type")
    fields: list[dict[str, Any]] = []
    if stype == "object":
        for name, sub in (schema.get("properties") or {}).items():
            path = f"{prefix}.{name}" if prefix else name
            sub_type = sub.get("type", "string")
            if sub_type in {"object", "array"}:
                fields.extend(json_schema_to_fields(sub, path))
            else:
                fields.append({"name": path, "type": sub_type, "nullable": True, "description": None})
    elif stype == "array":
        arr_prefix = f"{prefix}[]" if prefix else "[]"
        items = schema.get("items", {})
        item_type = items.get("type", "string")
        if item_type in {"object", "array"}:
            fields.extend(json_schema_to_fields(items, arr_prefix))
        else:
            fields.append({"name": arr_prefix, "type": item_type, "nullable": True, "description": None})
    return fields
