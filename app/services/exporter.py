from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import yaml

from .db import list_meta_objects


@dataclass
class MetaMappingChoice:
    meta_id: int
    mapping_name: str
    source_type: str
    source_meta_name: str
    destination_meta_name: str


def get_meta_mapping_choices() -> list[MetaMappingChoice]:
    metas = list_meta_objects()
    choices: list[MetaMappingChoice] = []
    for mo in metas:
        name = (
            f"{mo.source_meta_name}_to_{mo.destination_meta_name}"
            .replace(".", "_")
            .replace(":", "_")
        )
        choices.append(
            MetaMappingChoice(
                meta_id=mo.id,
                mapping_name=name,
                source_type=mo.source_type,
                source_meta_name=mo.source_meta_name,
                destination_meta_name=mo.destination_meta_name,
            )
        )
    return sorted(choices, key=lambda c: c.meta_id)


def has_exportable_meta_rows(meta_id: int) -> bool:
    metas = list_meta_objects()
    mo = next((m for m in metas if m.id == meta_id), None)
    if mo is None:
        return False
    return any(e.destination_field and e.source_field for e in mo.entries)


def build_meta_mapping_payload(meta_id: int) -> dict[str, Any]:
    metas = list_meta_objects()
    mo = next((m for m in metas if m.id == meta_id), None)
    if mo is None:
        raise FileNotFoundError("Selected meta mapping was not found.")

    entries = [e for e in mo.entries if e.destination_field and e.source_field]
    if not entries:
        raise ValueError("Selected meta mapping does not contain field mappings.")

    mapping_body: dict[str, dict[str, Any]] = {}
    for e in entries:
        entry: dict[str, Any] = {"source": e.source_field}
        if e.expression:
            entry["expression"] = e.expression
        mapping_body[e.destination_field] = entry

    return {
        "source": {
            "meta_name": mo.source_meta_name,
            "type": mo.source_type,
        },
        "destination": {
            "meta_name": mo.destination_meta_name,
        },
        "mapping": mapping_body,
    }


def serialize_export_payload(payload: dict[str, Any], export_format: str) -> tuple[str, str]:
    if export_format == "JSON":
        return json.dumps(payload, indent=2, ensure_ascii=False), "application/json"
    if export_format == "YAML":
        class _LiteralSafeDumper(yaml.SafeDumper):
            pass

        def _str_presenter(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        _LiteralSafeDumper.add_representer(str, _str_presenter)
        return yaml.dump(payload, Dumper=_LiteralSafeDumper, sort_keys=False, allow_unicode=True), "application/x-yaml"
    raise ValueError("Please select export format.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    return out
