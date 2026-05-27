"""Unit tests for import_sources_and_destinations.

All DB calls are mocked — no database connection is required.
"""
from __future__ import annotations

from itertools import count
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest

from app.services.importer import import_sources_and_destinations

# ---------------------------------------------------------------------------
# Patch targets (imported names inside the importer module)
# ---------------------------------------------------------------------------
_UPSERT_SOURCE = "app.services.importer.save_source"
_UPSERT_DESTINATION = "app.services.importer.save_destination"
_UPSERT_MAPPING = "app.services.importer.upsert_mapping_object"
_DELETE_SOURCE = "app.services.importer.delete_source"
_DELETE_DESTINATION = "app.services.importer.delete_destination"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _id_counter():
    """Returns a side_effect function that yields unique integer IDs per call."""
    c = count(1)
    return lambda *_, **__: next(c)


def _pg_row(
    *,
    cluster: str = "dc1",
    server: str = "pg-server",
    database: str = "mydb",
    schema: str = "public",
    table: str = "users",
    dest_server: str = "ch-server",
    dest_database: str = "analytics",
    dest_table: str = "users",
) -> dict:
    return {
        "source_type": "postgres",
        "cluster_name": cluster,
        "source_server": server,
        "source_database": database,
        "source_schema": schema,
        "source_table": table,
        "destination_server": dest_server,
        "destination_database": dest_database,
        "destination_table": dest_table,
    }


def _kafka_row(
    *,
    cluster: str = "kafka-prod",
    brokers: str = "broker1:9092",
    topic: str = "events.created",
    dest_server: str = "ch-server",
    dest_database: str = "analytics",
    dest_table: str = "events",
) -> dict:
    return {
        "source_type": "kafka",
        "cluster_name": cluster,
        "source_kafka_brokers": brokers,
        "source_kafka_topic": topic,
        "destination_server": dest_server,
        "destination_database": dest_database,
        "destination_table": dest_table,
    }


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# PostgreSQL source imports
# ---------------------------------------------------------------------------

class TestPostgresImport:

    def test_single_row_creates_one_source_one_destination_one_mapping(self):
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([_pg_row()]), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 1
        assert result["total_records"] == 1
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 1

    def test_two_distinct_sources_same_destination(self):
        rows = [
            _pg_row(table="orders", dest_table="orders"),
            _pg_row(table="payments", dest_table="orders"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 2
        assert result["total_destinations"] == 1
        assert result["total_records"] == 2
        assert mock_src.call_count == 2
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 2

    def test_one_source_two_distinct_destinations(self):
        rows = [
            _pg_row(table="orders", dest_table="orders_raw"),
            _pg_row(table="orders", dest_table="orders_enriched"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 2
        assert result["total_records"] == 2
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 2
        assert mock_map.call_count == 2

    def test_duplicate_rows_are_deduplicated(self):
        """Two identical rows must produce a single source, destination, and mapping."""
        rows = [_pg_row(), _pg_row()]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 1
        assert result["total_records"] == 1
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 1

    def test_multiple_sources_multiple_destinations(self):
        rows = [
            _pg_row(table="orders", dest_table="orders"),
            _pg_row(table="payments", dest_table="payments"),
            _pg_row(table="refunds", dest_table="payments"),  # 2nd source -> same dest as payments
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 3
        assert result["total_destinations"] == 2
        assert result["total_records"] == 3
        assert mock_src.call_count == 3
        assert mock_dest.call_count == 2
        assert mock_map.call_count == 3

    def test_multi_source_destinations_count(self):
        """Destinations with more than one source should be reflected in multi_source_destinations."""
        rows = [
            _pg_row(table="orders", dest_table="shared"),
            _pg_row(table="payments", dest_table="shared"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()),
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()),
            patch(_UPSERT_MAPPING),
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "postgres")

        assert result["multi_source_destinations"] == 1

    def test_delete_called_for_each_unique_source_and_destination(self):
        rows = [
            _pg_row(table="orders", dest_table="orders"),
            _pg_row(table="payments", dest_table="payments"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()),
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()),
            patch(_UPSERT_MAPPING),
            patch(_DELETE_SOURCE) as mock_del_src,
            patch(_DELETE_DESTINATION) as mock_del_dest,
        ):
            import_sources_and_destinations(_df(rows), "postgres")

        assert mock_del_src.call_count == 2
        assert mock_del_dest.call_count == 2


# ---------------------------------------------------------------------------
# Kafka source imports
# ---------------------------------------------------------------------------

class TestKafkaImport:

    def test_single_row_creates_one_source_one_destination_one_mapping(self):
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([_kafka_row()]), "kafka")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 1
        assert result["total_records"] == 1
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 1

    def test_two_topics_same_destination(self):
        rows = [
            _kafka_row(topic="events.created", dest_table="events"),
            _kafka_row(topic="events.updated", dest_table="events"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "kafka")

        assert result["ok"] is True
        assert result["total_sources"] == 2
        assert result["total_destinations"] == 1
        assert result["total_records"] == 2
        assert mock_src.call_count == 2
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 2

    def test_one_topic_two_destinations(self):
        rows = [
            _kafka_row(topic="events.created", dest_table="events_raw"),
            _kafka_row(topic="events.created", dest_table="events_enriched"),
        ]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "kafka")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 2
        assert result["total_records"] == 2
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 2
        assert mock_map.call_count == 2

    def test_duplicate_rows_are_deduplicated(self):
        rows = [_kafka_row(), _kafka_row()]
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(rows), "kafka")

        assert result["ok"] is True
        assert result["total_sources"] == 1
        assert result["total_destinations"] == 1
        assert result["total_records"] == 1
        assert mock_src.call_count == 1
        assert mock_dest.call_count == 1
        assert mock_map.call_count == 1


# ---------------------------------------------------------------------------
# Validation and error handling
# ---------------------------------------------------------------------------

class TestValidationAndErrors:

    def test_unsupported_source_type_returns_error_without_db_calls(self):
        # Row source_type must match the declared import type so validation passes,
        # then get_source_import_strategy returns None for an unknown type.
        row = {
            "source_type": "oracle",
            "destination_server": "ch-server",
            "destination_database": "analytics",
            "destination_table": "users",
        }
        with (
            patch(_UPSERT_SOURCE) as mock_src,
            patch(_UPSERT_DESTINATION) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([row]), "oracle")

        assert result["ok"] is False
        assert any("Unsupported source type" in e for e in result["errors"])
        mock_src.assert_not_called()
        mock_dest.assert_not_called()
        mock_map.assert_not_called()

    def test_wrong_source_type_in_row_returns_error_without_db_calls(self):
        """Rows whose source_type column doesn't match the declared import type fail validation."""
        row = _pg_row()
        row["source_type"] = "kafka"  # mismatch: importing as postgres
        with (
            patch(_UPSERT_SOURCE) as mock_src,
            patch(_UPSERT_DESTINATION) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([row]), "postgres")

        assert result["ok"] is False
        assert len(result["errors"]) >= 1
        mock_src.assert_not_called()
        mock_dest.assert_not_called()
        mock_map.assert_not_called()

    def test_kafka_row_missing_topic_returns_error(self):
        row = _kafka_row()
        row["source_kafka_topic"] = ""
        with (
            patch(_UPSERT_SOURCE) as mock_src,
            patch(_UPSERT_DESTINATION) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([row]), "kafka")

        assert result["ok"] is False
        assert any("source_kafka_topic" in e for e in result["errors"])
        mock_src.assert_not_called()
        mock_dest.assert_not_called()
        mock_map.assert_not_called()

    def test_postgres_row_with_dot_in_table_name_returns_error(self):
        row = _pg_row(table="public.orders")  # dot in table name is invalid
        with (
            patch(_UPSERT_SOURCE) as mock_src,
            patch(_UPSERT_DESTINATION) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([row]), "postgres")

        assert result["ok"] is False
        assert any("source_table" in e for e in result["errors"])
        mock_src.assert_not_called()
        mock_dest.assert_not_called()
        mock_map.assert_not_called()

    def test_empty_dataframe_returns_success_with_zero_counts(self):
        """An empty (but structurally valid) dataframe produces zero records."""
        empty_rows: list[dict] = []
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()) as mock_src,
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()) as mock_dest,
            patch(_UPSERT_MAPPING) as mock_map,
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df(empty_rows), "postgres")

        assert result["ok"] is True
        assert result["total_sources"] == 0
        assert result["total_destinations"] == 0
        assert result["total_records"] == 0
        mock_src.assert_not_called()
        mock_dest.assert_not_called()
        mock_map.assert_not_called()

    def test_whitespace_in_column_names_is_normalized(self):
        """Extra whitespace in DataFrame column names must not break import."""
        row = {
            "  source_type  ": "postgres",
            " cluster_name ": "dc1",
            " source_server ": "pg-server",
            " source_database ": "mydb",
            " source_schema ": "public",
            " source_table ": "users",
            " destination_server ": "ch-server",
            " destination_database ": "analytics",
            " destination_table ": "users",
        }
        with (
            patch(_UPSERT_SOURCE, side_effect=_id_counter()),
            patch(_UPSERT_DESTINATION, side_effect=_id_counter()),
            patch(_UPSERT_MAPPING),
            patch(_DELETE_SOURCE),
            patch(_DELETE_DESTINATION),
        ):
            result = import_sources_and_destinations(_df([row]), "postgres")

        assert result["ok"] is True
        assert result["total_records"] == 1
