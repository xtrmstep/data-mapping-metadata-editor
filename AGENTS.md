# Agent Instructions — Data Mapping Metadata Editor

## Project Concept

This is a **lightweight Streamlit application** for managing source-to-lakehouse field mappings.
It is used by data engineers to:

1. Import source metadata and schema descriptions from uploaded files.
2. Browse and edit source and destination object definitions.
3. Author field-level mapping rules between sources and lakehouse destination tables.
4. Export completed mappings to files.

The tool is intentionally simple — no auth, no background jobs.
All persistent data (sources, destinations, schemas, and mappings) is stored in PostgreSQL via a SQLAlchemy ORM layer.

---

## High-Level Architecture

```text
app/                        # Application source code root
  models/
    orm.py                  # SQLAlchemy ORM models: Source, Destination, SourceSchema, DestinationSchema, MappingObject, MappingField, MappingMetaObject, MappingMetaEntry
  pages/                    # User-facing pages for import, browsing, editing, export, and graph visualisation
    05_mapping_editor.py    # Field-level mapping editor (tab 1) + Meta Mapping editor with refresh, schema upload, and meta field mappings (tab 2)
    06_mapping_graph.py     # Graphviz visualisation of source→destination mappings with source and destination filters
  services/
    db.py                   # ORM-based CRUD operations (engine, session, upsert/list/delete functions)
    importer.py             # CSV import logic, JSON schema flattening
    exporter.py             # Export payload builder and serialiser (JSON/YAML)
    common.py               # SOURCE_TYPE_OPTIONS constant shared by services and pages
    validators.py           # Column presence and value validation helpers
    storage.py              # Export file I/O (save_export only)
imports/                    # Sample input files for sources, schemas, and destinations
```

Runtime data for mappings and exports is created on demand by the app and is not part of the checked-in repository layout. Sources and destinations are persisted entirely in PostgreSQL — no YAML/CSV metadata files are written during import.

---

## Main Application Flow

1. The user imports sources by uploading files with source information. This source information also includes the related destination information.
2. The system registers the source and destination, then immediately creates a draft mapping record between this source and destination.
3. A source can be either a Postgres table or a Kafka topic. The destination is always a ClickHouse table.
4. Initially, the source and destination do not contain schema information. After they are created, the user can upload schema descriptions for both the source
   and the destination.
5. When a schema is uploaded, it is added to the related source or destination.
6. If a mapping does not exist yet, schema upload does not affect it. If a mapping already exists, it is cleared and must be configured again.
7. When source or destination information is re-uploaded, all related information is overwritten. There is no partial update mode.
8. Once both source and destination schemas are available, the user can configure the mapping.
9. Mapping is configured from the destination side: for each destination field, the user selects which source field or logic should populate it.
10. A mapping can be direct field-to-field mapping, or it can use custom logic based on one or more source fields.
11. The completed mapping is saved in the mapping record between the source and destination.
12. The mapping can be exported to a file.

---

## Technologies in Use

- Python powers the application logic.
- Streamlit provides the user interface.
- PostgreSQL is used for full persistence of all domain objects.
- SQLAlchemy 2.x ORM is the data access layer (`app/models/orm.py` + `app/services/db.py`).
- ClickHouse is the destination platform.
- Source systems can be PostgreSQL tables or Kafka topics.
- Docker Compose is available for containerized local runs.
- `uv` is used for local Python environment and dependency management.

---

## Agent Guidelines

- PostgreSQL is used for **full source and destination persistence** via SQLAlchemy ORM. All tables are created automatically by `Base.metadata.create_all` on first connection.
- **ORM table names:** `source`, `destination`, `source_schema`, `destination_schema`, `mapping_object`, `mapping_field`, `mapping_meta_object`, `mapping_meta_entry` (singular, code-first).
- **Meta object natural keys:** `destination_meta_name = "{database}.{table_name}"` groups destinations sharing the same database and table name across clusters/servers. `source_meta_name = "{database}.{schema}.{table_name}"` (postgres) or `"kafka:{topic}"` (kafka) groups sources similarly.
- **Meta object schema columns:** `destination_schema_json` and `source_schema_json` are JSON list columns on `mapping_meta_object`. Set via `update_meta_destination_schema` / `update_meta_source_schema`; both update all rows sharing the same meta name.
- **Source key** is the unique natural key derived at import time: `{database}_{schema}_{table}` for Postgres, `{topic}` for Kafka.
- **Destination natural key** is `(cluster_name, server, database, table_name)` — enforced by `uq_destination_natural_key` unique constraint. The same table name on different clusters, servers, or databases is treated as a distinct destination.
- **Do not add authentication.** This is a local/internal tool.
- **Keep pages independent.** Each page under `app/pages/` is self-contained — shared logic belongs in `services/` or `models/`.
- **Models are pure.** `app/models/orm.py` must not import from `services/` or perform I/O. Models may define `identity_clauses()` instance methods returning SQLAlchemy filter conditions for natural-key lookups.
- **Entity identity is owned by models.** `Source.identity_clauses()` encapsulates Kafka-vs-Postgres lookup rules; `Destination.identity_clauses()` encapsulates the `(server, database, table_name)` natural key. `db.py` calls these methods and must not duplicate the logic.
- **`db.py` is a pure data-access layer.** Functions are named `save_source`, `delete_source`, `save_destination`, `delete_destination`, `save_mapping_field`, `delete_mapping_fields(mapping_object_id)`. No source-type branching or business rules belong here.
- **`importer.py` owns import business logic.** Strategy classes call `save_source`/`delete_source` directly; `insert_sources_and_destinations` calls `save_destination`/`delete_destination`.
- **All file I/O goes through `storage.py`.** Do not use raw `open()` calls in pages or services other than `storage.py`. Note: all domain data is stored in PostgreSQL — `storage.py` is reserved for export file output only.
- **ORM models are the source of truth** for field shapes. Update `orm.py` before updating service or UI code.
- **Page ordering is controlled by filename prefix** (`01_`, `02_`, …). Preserve this when adding pages.
- **Do not commit generated runtime data.** Imported objects, mappings, and exports are runtime output.
- When adding a new service function, keep it in the relevant `services/` module; do not create new top-level modules.
- When modifying the import flow, test against the sample files under `imports/`.

---

## Maintaining This File

This file is the authoritative reference for any agent working in this repository.
Keep it accurate and up to date as the project evolves.

**When to update this file:**

- A new page is added to `app/pages/` → update the architecture tree and page list.
- A new service module or helper is introduced → add it to the architecture tree with a one-line description.
- An ORM model is added, renamed, or restructured → update the model references and Agent Guidelines table names.
- The import flow changes → update the Main Application Flow section.
- The storage layout changes (new directory, renamed path) → update the architecture tree and any affected path examples.
- The technology stack changes → update the Technologies in Use section.

**How to update:**

1. Make the code change first; update this file immediately after in the same task.
2. Keep descriptions concise — one line per item in the architecture tree and short bullets for workflow changes.
3. Do not add speculative or aspirational content — only document what is actually implemented.
