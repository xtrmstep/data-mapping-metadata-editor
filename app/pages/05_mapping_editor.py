import pandas as pd
import streamlit as st

from app.services.db import (
    delete_meta_entries,
    list_meta_objects,
    rebuild_meta_objects,
    save_meta_entry,
    update_meta_destination_schema,
    update_meta_source_schema,
)

st.set_page_config(page_title="Data Mapping Editor", layout="wide")
st.title("Data Mapping Editor")

META_EXPR_TOKEN = "{{source_field}}"


def _to_bool(v: object) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _parse_schema_csv(uploaded_file) -> list[dict] | None:
    """Parse an uploaded schema CSV into a list of field dicts.

    Expected columns: field_name, field_type, nullable, description
    Returns None and shows an error if parsing fails.
    """
    try:
        df = pd.read_csv(uploaded_file).fillna("")
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        return None
    fields = []
    for _, row in df.iterrows():
        name = str(row.get("field_name") or "").strip()
        if not name:
            continue
        fields.append({
            "name": name,
            "type": str(row.get("field_type") or "String").strip(),
            "nullable": _to_bool(row.get("nullable", "true")),
            "description": str(row.get("description") or "").strip() or None,
        })
    if not fields:
        st.error("No valid rows found in CSV. Expected column: field_name.")
        return None
    return fields

# ── Refresh ────────────────────────────────────────────────────────────────────
st.caption("Meta objects group physical tables/topics that share the same logical identity across clusters and servers.")
st.caption("Refreshing rebuilds the list from current import data and clears all previous meta objects and their mappings.")
if st.button("Refresh metadata", type="primary"):
    count = rebuild_meta_objects()
    st.success(f"Rebuilt {count} meta object(s).")
    st.rerun()

meta_objects = list_meta_objects()
if not meta_objects:
    st.info("No meta objects found. Click **Refresh metadata** to build them from import data.")
    st.stop()

# ── Meta mapping editor ────────────────────────────────────────────────────────
st.divider()
st.subheader("Meta field mappings")

dest_meta_names_sorted = sorted({mo.destination_meta_name for mo in meta_objects})

sel_meta_dst = st.selectbox(
    "Destination meta object", options=dest_meta_names_sorted, key="meta_sel_dst"
)

dst_meta_mos = [mo for mo in meta_objects if mo.destination_meta_name == sel_meta_dst]
src_options  = [mo.source_meta_name for mo in dst_meta_mos]
if not src_options:
    st.info("No source meta objects for this destination.")
    st.stop()

sel_meta_src = st.selectbox(
    "Source meta object", options=src_options, key="meta_sel_src"
)

selected_meta_mo = next(
    (mo for mo in dst_meta_mos if mo.source_meta_name == sel_meta_src), None
)
if selected_meta_mo is None:
    st.info("Select a valid source meta object.")
    st.stop()

meta_dst_fields = [f["name"] for f in (selected_meta_mo.destination_schema_json or [])]
meta_src_fields = [f["name"] for f in (selected_meta_mo.source_schema_json or [])]

_dst_schema_label = (
    f"Destination schema — {sel_meta_dst} ({len(meta_dst_fields)} fields)"
    if meta_dst_fields else f"Destination schema — {sel_meta_dst} ⚠ missing"
)
with st.expander(_dst_schema_label, expanded=not meta_dst_fields):
    st.caption("CSV columns: field_name, field_type, nullable, description. Updates all meta objects sharing this destination name.")
    dst_schema_file = st.file_uploader("Schema CSV", type=["csv"], key="meta_dst_schema_file")
    if dst_schema_file is not None:
        _dst_preview = pd.read_csv(dst_schema_file).fillna("")
        st.dataframe(_dst_preview, use_container_width=True, hide_index=True)
        dst_schema_file.seek(0)
        if st.button("Apply destination schema", key="apply_dst_schema"):
            fields = _parse_schema_csv(dst_schema_file)
            if fields is not None:
                updated = update_meta_destination_schema(sel_meta_dst, fields)
                st.success(f"Updated destination schema on {updated} meta object(s).")
                st.rerun()

_src_schema_label = (
    f"Source schema — {sel_meta_src} ({len(meta_src_fields)} fields)"
    if meta_src_fields else f"Source schema — {sel_meta_src} ⚠ missing"
)
with st.expander(_src_schema_label, expanded=not meta_src_fields):
    st.caption("CSV columns: field_name, field_type, nullable, description. Updates all meta objects sharing this source name.")
    src_schema_file = st.file_uploader("Schema CSV", type=["csv"], key="meta_src_schema_file")
    if src_schema_file is not None:
        _src_preview = pd.read_csv(src_schema_file).fillna("")
        st.dataframe(_src_preview, use_container_width=True, hide_index=True)
        src_schema_file.seek(0)
        if st.button("Apply source schema", key="apply_src_schema"):
            fields = _parse_schema_csv(src_schema_file)
            if fields is not None:
                updated = update_meta_source_schema(sel_meta_src, fields)
                st.success(f"Updated source schema on {updated} meta object(s).")
                st.rerun()

if not meta_dst_fields or not meta_src_fields:
    st.stop()

_meta_id = selected_meta_mo.id
meta_target_to_source: dict[str, str] = {}
meta_target_to_expr: dict[str, str] = {}
for entry in selected_meta_mo.entries:
    meta_target_to_source[entry.destination_field] = entry.source_field or ""
    meta_target_to_expr[entry.destination_field]   = entry.expression or ""

for entry in selected_meta_mo.entries:
    st.session_state[f"meta_src__{_meta_id}__{entry.destination_field}"]  = entry.source_field or ""
    st.session_state[f"meta_expr__{_meta_id}__{entry.destination_field}"] = entry.expression or ""


def _save_meta_assignment(destination_field: str) -> None:
    src_key  = f"meta_src__{_meta_id}__{destination_field}"
    expr_key = f"meta_expr__{_meta_id}__{destination_field}"
    new_source = str(st.session_state.get(src_key) or "").strip()
    expression = str(st.session_state.get(expr_key) or "").strip()

    if expression and META_EXPR_TOKEN not in expression:
        st.warning(
            f"Expression for '{destination_field}' should include "
            f"{META_EXPR_TOKEN} to reference the source value."
        )

    if not new_source:
        return

    save_meta_entry(
        _meta_id,
        destination_field,
        source_field=new_source,
        expression=expression,
    )


st.caption("Mappings are saved automatically when source field or expression is changed.")
st.caption(f"Use {META_EXPR_TOKEN} inside expression to reference source field value.")

btn_col1, btn_col2 = st.columns([1, 5])
with btn_col1:
    if st.button("Auto-map by name", key="meta_automap"):
        src_lower = {f.lower(): f for f in meta_src_fields}
        for dst_field in meta_dst_fields:
            matched = src_lower.get(dst_field.lower())
            if matched:
                st.session_state[f"meta_src__{_meta_id}__{dst_field}"] = matched
                save_meta_entry(_meta_id, dst_field, source_field=matched, expression="")
        st.rerun()
with btn_col2:
    if st.button("Clear all mappings", key="meta_clear"):
        delete_meta_entries(_meta_id)
        st.rerun()

for dst_field in meta_dst_fields:
    src_key  = f"meta_src__{_meta_id}__{dst_field}"
    expr_key = f"meta_expr__{_meta_id}__{dst_field}"

    current_source = meta_target_to_source.get(dst_field, "")
    current_expr   = meta_target_to_expr.get(dst_field, "")

    meta_currently_used = {
        src for tgt, src in meta_target_to_source.items()
        if tgt != dst_field and src
    }
    meta_available = [""] + [
        f for f in meta_src_fields if f not in meta_currently_used or f == current_source
    ]

    if src_key not in st.session_state:
        st.session_state[src_key] = current_source
    if st.session_state[src_key] not in meta_available:
        st.session_state[src_key] = ""

    if expr_key not in st.session_state:
        st.session_state[expr_key] = current_expr

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.text_input(
            "Destination field",
            value=dst_field,
            key=f"meta_dst__{_meta_id}__{dst_field}",
            disabled=True,
        )
    with col2:
        st.selectbox(
            "Source field",
            options=meta_available,
            key=src_key,
            on_change=_save_meta_assignment,
            args=(dst_field,),
        )
    with col3:
        st.text_input(
            "Expression",
            key=expr_key,
            on_change=_save_meta_assignment,
            args=(dst_field,),
            placeholder=f"e.g. toInt64({META_EXPR_TOKEN})",
        )

