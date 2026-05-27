import streamlit as st

from app.services.exporter import (
    build_meta_mapping_payload,
    get_meta_mapping_choices,
    has_exportable_meta_rows,
    serialize_export_payload,
)

st.set_page_config(page_title="Data Mapping Metadata Editor", layout="wide")
st.title("Export Mapping")

choices = get_meta_mapping_choices()
if not choices:
    st.info("No meta mappings found. Use the Mapping Editor page to build and configure meta objects.")
    st.stop()

exportable_choices = [c for c in choices if has_exportable_meta_rows(c.meta_id)]
if not exportable_choices:
    st.info("No meta mappings with configured field-level definitions are available for export.")
    st.stop()

header_cols = st.columns([5, 1, 1, 1])
header_cols[0].caption("**Mapping**")
header_cols[1].caption("**JSON**")
header_cols[2].caption("**YAML**")
header_cols[3].caption("**Edit**")

st.divider()

for idx, choice in enumerate(exportable_choices):
    try:
        payload = build_meta_mapping_payload(choice.meta_id)
    except Exception:
        continue

    json_content, json_mime = serialize_export_payload(payload, "JSON")
    yaml_content, yaml_mime = serialize_export_payload(payload, "YAML")

    col_label, col_json, col_yaml, col_edit = st.columns([5, 1, 1, 1])

    with col_label:
        st.markdown(f"**{choice.source_meta_name} → {choice.destination_meta_name}**")
        st.caption(f"`{choice.source_type}`")

    with col_json:
        st.download_button(
            "JSON",
            data=json_content,
            file_name=f"{choice.mapping_name}.json",
            mime=json_mime,
            key=f"json_{idx}_{choice.meta_id}",
        )

    with col_yaml:
        st.download_button(
            "YAML",
            data=yaml_content,
            file_name=f"{choice.mapping_name}.yaml",
            mime=yaml_mime,
            key=f"yaml_{idx}_{choice.meta_id}",
        )

    with col_edit:
        if st.button("Edit", key=f"edit_{idx}_{choice.meta_id}"):
            st.session_state["meta_sel_dst"] = choice.destination_meta_name
            st.session_state["meta_sel_src"] = choice.source_meta_name
            st.switch_page("pages/05_mapping_editor.py")

    if idx < len(exportable_choices) - 1:
        st.divider()
