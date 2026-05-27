import streamlit as st
import pandas as pd

from app.services.db import delete_mapping_fields, list_destination_cluster_names, list_destination_server_names, list_destination_table_names, list_destinations, list_mapping_objects, update_destination_schema

st.set_page_config(page_title="Data Mapping Metadata Editor", layout="wide")
st.title("Destinations")

_col_cluster, _col_server, _col_table, _ = st.columns(4)

_cluster_names = list_destination_cluster_names()
with _col_cluster:
    dest_cluster = st.selectbox(
        "Cluster",
        options=[None, *_cluster_names],
        format_func=lambda v: "All" if v is None else v,
        help="Filter destinations by cluster.",
    )

_server_names = list_destination_server_names(dest_cluster)
with _col_server:
    dest_server = st.selectbox(
        "Server",
        options=[None, *_server_names],
        format_func=lambda v: "All" if v is None else v,
        help="Filter destinations by server.",
    )

_table_names = list_destination_table_names(dest_cluster, dest_server)
with _col_table:
    dest_table = st.selectbox(
        "Table",
        options=[None, *_table_names],
        format_func=lambda v: "All" if v is None else v,
        help="Filter destinations by table name.",
    )

destination_rows = list_destinations(dest_cluster, dest_server, dest_table)

if not destination_rows:
    st.info("No destination metadata found.")
    st.stop()

table_rows = []
for d in destination_rows:
    table_rows.append(
        {
            "cluster": d.cluster_name,
            "server": d.server,
            "database": d.database,
            "table": d.table_name,
            "field_count": len(d.schema_fields),
            "_destination_id": d.id,
        }
    )

df = pd.DataFrame(table_rows)

st.markdown("### Uploaded destinations")
selection_event = st.dataframe(
    df.drop(columns=["_destination_id"]),
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="destinations_table",
)

selected_rows = selection_event.selection.get("rows", []) if selection_event else []
if selected_rows:
    st.session_state.selected_destination_id = df.iloc[selected_rows[0]]["_destination_id"]
else:
    st.session_state.pop("selected_destination_id", None)

selected_destination_id = st.session_state.get("selected_destination_id")

if selected_destination_id is None:
    st.info("Select a destination row to view its schema and upload schema information.")
    st.stop()

selected = next((d for d in destination_rows if d.id == selected_destination_id), None)
if selected is None:
    st.info("Select a destination row to view its schema and upload schema information.")
    st.stop()

st.markdown(f"### Schema preview: `{selected.table_name}`")
if selected.schema_fields:
    schema_display = [
        {"Field name": f.field_name, "Data type": f.field_type, "Nullable": f.nullable}
        for f in selected.schema_fields
    ]
    st.dataframe(pd.DataFrame(schema_display), use_container_width=True, hide_index=True)
else:
    st.info("No schema information has been uploaded for this destination.")

schema_csv = st.file_uploader("Upload destination table schema CSV", type=["csv"])
if schema_csv is not None:
    fdf = pd.read_csv(schema_csv).fillna("")
    st.dataframe(fdf, use_container_width=True)
    if st.button("Save destination schema", type="primary"):
        new_fields = []
        for _, r in fdf.iterrows():
            name = str(r.get("field_name") or r.get("name") or "").strip()
            if not name:
                continue
            new_fields.append(
                {
                    "name": name,
                    "type": str(r.get("field_type") or r.get("type") or "String").strip(),
                    "nullable": str(r.get("nullable", "true")).strip().lower() in {"1", "true", "yes", "y"},
                    "description": str(r.get("description") or "").strip() or None,
                }
            )
        update_destination_schema(selected_destination_id, new_fields)
        for mo in list_mapping_objects():
            if mo.destination.id == selected_destination_id:
                delete_mapping_fields(mo.id)
        st.success(f"Updated destination schema for {selected.table_name} ({len(new_fields)} fields)")
