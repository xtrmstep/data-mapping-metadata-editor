from typing import Callable

from .common import SOURCE_TYPE_OPTIONS


def _contains_dot(value: object) -> bool:
    return "." in str(value or "").strip()


def validate_import_columns(columns: list[str], source_type: str) -> list[str]:
    config = next((v for v in SOURCE_TYPE_OPTIONS.values() if v["source_type"] == source_type), None)
    expected = {col["name"] for col in config["columns"]} if config else set()
    missing = expected.difference(set(columns))
    return sorted(missing)


def _validate_kafka_row(row: dict) -> list[str]:
    errors: list[str] = []
    if not str(row.get("source_kafka_topic") or "").strip():
        errors.append("source_kafka_topic must not be empty")
    return errors


def _validate_postgres_row(row: dict) -> list[str]:
    errors: list[str] = []
    for col in ["source_database", "source_schema", "source_table"]:
        if _contains_dot(row.get(col)):
            errors.append(f"{col} must not contain dots")
    return errors


_ROW_VALIDATORS: dict[str, Callable] = {
    "kafka": _validate_kafka_row,
    "postgres": _validate_postgres_row,
}


def validate_import_row(row: dict, source_type: str) -> list[str]:
    validator = _ROW_VALIDATORS.get(source_type)
    errors = validator(row) if validator else []

    for col in ["destination_database", "destination_table"]:
        if _contains_dot(row.get(col)):
            errors.append(f"{col} must not contain dots")

    return errors


def validate_mapping_row(row: dict) -> list[str]:
    errors = []
    if not row.get("source_object"):
        errors.append("source_object must not be empty")
    if not row.get("source_field"):
        errors.append("source_field must not be empty")
    if not row.get("target_table"):
        errors.append("target_table must not be empty")
    if not row.get("destination_field"):
        errors.append("destination_field must not be empty")
    return errors
