import json

import pandas as pd
import streamlit as st

from app.services.db import delete_mapping_fields, list_cluster_names, list_database_names, list_mapping_objects, list_schema_names, list_server_names, list_source_types, list_sources, list_table_names, update_source_schema
from app.services.importer import json_schema_to_fields


st.set_page_config(page_title="Data Mapping Metadata Editor", layout="wide")


def _to_bool(v: object) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


st.title("Sources")
st.caption("Table view for uploaded sources with per-object schema preview and upload.")

_source_types = list_source_types()
if not _source_types:
    st.info("No source metadata found. Import CSV first.")
    st.stop()

_col_type, _col_cluster = st.columns(2)
with _col_type:
    source_type = st.radio(
        "Source type",
        options=_source_types,
        horizontal=True,
        help="Select the source type to filter the displayed sources. This is based on the 'source_type' field in the imported metadata.",
    )

if source_type != "kafka":
    _col_cluster, _col_server, _col_database, _col_schema, _col_table = st.columns(5)
else:
    _col_cluster, _, _, _, _ = st.columns(5)

_cluster_names = list_cluster_names(source_type)
with _col_cluster:
    cluster_name = st.selectbox(
        "Cluster",
        options=[None, *_cluster_names],
        format_func=lambda v: "All" if v is None else v,
        help="Filter sources by cluster name.",
    )

if source_type != "kafka":
    _server_names = list_server_names(source_type, cluster_name)
    with _col_server:
        server_name = st.selectbox(
            "Server",
            options=[None, *_server_names],
            format_func=lambda v: "All" if v is None else v,
            help="Filter sources by server.",
        )

    _database_names = list_database_names(source_type, cluster_name, server_name)
    with _col_database:
        database_name = st.selectbox(
            "Database",
            options=[None, *_database_names],
            format_func=lambda v: "All" if v is None else v,
            help="Filter sources by database.",
        )

    _schema_names = list_schema_names(source_type, cluster_name, server_name, database_name)
    with _col_schema:
        schema_name = st.selectbox(
            "Schema",
            options=[None, *_schema_names],
            format_func=lambda v: "All" if v is None else v,
            help="Filter sources by schema.",
        )

    _table_names = list_table_names(source_type, cluster_name, server_name, database_name, schema_name)
    with _col_table:
        table_name = st.selectbox(
            "Table",
            options=[None, *_table_names],
            format_func=lambda v: "All" if v is None else v,
            help="Filter sources by table name.",
        )
else:
    server_name = None
    database_name = None
    schema_name = None
    table_name = None

source_rows = list_sources(source_type, cluster_name, server_name, database_name, schema_name, table_name)

if not source_rows:
    st.info("No sources found for this source type.")
    st.stop()

table_rows = []
for s in source_rows:
    if source_type == "kafka":
        row = {
            "cluster": s.cluster_name,
            "kafka": s.kafka,
            "brokers": s.brokers,
            "topic": s.topic,
            "field_count": len(s.schema_fields),
            "_source_id": s.id,
        }
    else:
        row = {
            "cluster": s.cluster_name,
            "server": s.server,
            "database": s.database,
            "schema": s.pg_schema,
            "table": s.table_name,
            "field_count": len(s.schema_fields),
            "_source_id": s.id,
        }
    table_rows.append(row)

df = pd.DataFrame(table_rows)

st.markdown("### Uploaded sources")
selection_event = st.dataframe(
    df.drop(columns=["_source_id"]),
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="sources_table",
)

selected_rows = selection_event.selection.get("rows", []) if selection_event else []
if selected_rows:
    st.session_state.selected_source_id = df.iloc[selected_rows[0]]["_source_id"]
else:
    st.session_state.pop("selected_source_id", None)

selected_source_id = st.session_state.get("selected_source_id")

if selected_source_id is None:
    st.info("Select a source row to view its schema and upload schema information.")
    st.stop()

selected = next((s for s in source_rows if s.id == selected_source_id), None)
if selected is None:
    st.info("Select a source row to view its schema and upload schema information.")
    st.stop()

st.markdown(f"### Schema preview: `{selected.table_name or selected.topic}`")
flat_fields = [
    {"name": f.field_name, "type": f.field_type, "nullable": f.nullable}
    for f in selected.schema_fields
]
if flat_fields:
    st.dataframe(pd.DataFrame(flat_fields), use_container_width=True, hide_index=True)
else:
    st.info("No schema information has been uploaded for this source.")

upload_mode = st.radio(
    "Schema upload format",
    options=["csv_fields", "json_schema"],
    horizontal=True,
)

if upload_mode == "csv_fields":
    st.caption("CSV columns: field_name, field_type, nullable, description")
    schema_csv = st.file_uploader("Upload schema CSV", type=["csv"])
    if schema_csv is not None:
        fdf = pd.read_csv(schema_csv).fillna("")
        st.dataframe(fdf, use_container_width=True)
        if st.button("Save schema CSV", type="primary"):
            fields = []
            for _, r in fdf.iterrows():
                fname = str(r.get("field_name") or r.get("source_field") or "").strip()
                if not fname:
                    continue
                fields.append(
                    {
                        "name": fname,
                        "type": str(r.get("field_type") or r.get("source_field_type") or "string").strip(),
                        "nullable": _to_bool(r.get("nullable", "true")),
                        "description": str(r.get("description") or "").strip() or None,
                    }
                )
            update_source_schema(selected_source_id, fields)
            for mo in list_mapping_objects():
                if mo.source.id == selected_source_id:
                    delete_mapping_fields(mo.id)
            st.success(f"Saved {len(fields)} fields.")
    else:
        st.warning("Upload a schema CSV to save fields for the selected source.")
else:
    schema_file = st.file_uploader("Upload JSON Schema", type=["json"])
    if schema_file is not None:
        raw_schema = schema_file.read().decode("utf-8")
        schema_doc = json.loads(raw_schema)
        detected = json_schema_to_fields(schema_doc)
        st.dataframe(pd.DataFrame(detected), use_container_width=True)
        if st.button("Save JSON Schema-derived fields", type="primary"):
            update_source_schema(selected_source_id, detected)
            for mo in list_mapping_objects():
                if mo.source.id == selected_source_id:
                    delete_mapping_fields(mo.id)
            st.success(f"Saved {len(detected)} flattened fields from JSON Schema.")
    else:
        st.warning("Upload a JSON Schema file for the selected source before saving.")
