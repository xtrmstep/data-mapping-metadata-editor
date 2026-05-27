import pandas as pd
import streamlit as st

from app.services.importer import import_sources_and_destinations, normalize_import_dataframe
from app.services.common import SOURCE_TYPE_OPTIONS
from app.services.validators import validate_import_columns

st.set_page_config(page_title="Data Mapping Metadata Editor", layout="wide")
st.title("Import Sources and Destinations")

selected_source_type = st.radio(
    "Select source type",
    options=list(SOURCE_TYPE_OPTIONS.keys()),
    index=None,
    horizontal=True,
)

if selected_source_type:
    selected_config = SOURCE_TYPE_OPTIONS[selected_source_type]
    st.markdown("**Expected CSV structure**")
    st.table(pd.DataFrame(selected_config["columns"]).rename(columns={"name": "Field", "description": "Description"}))
    st.caption(selected_config["note"])

st.info("Uploaded CSV files are processed in-memory and are **not stored on the server**.")

if not selected_source_type:
    st.warning("Select a source type to see the expected CSV structure and enable upload.")
else:
    uploaded_file = st.file_uploader("Upload source metadata CSV", type=["csv"])

    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file, nrows=5)  # Limit to first 5 rows for preview; adjust as needed
        df = normalize_import_dataframe(df_raw)
        st.subheader("Preview")
        st.dataframe(df, use_container_width=True)

        expected_source_type = selected_config["source_type"]
        missing = validate_import_columns(df.columns.tolist(), expected_source_type)
        if missing:
            st.error(f"Missing required columns: {', '.join(missing)}")
        else:
            st.success("Validation passed")

        if st.button("Import", type="primary"):
            # Reset file pointer to the beginning and re-read the full CSV for processing
            uploaded_file.seek(0)
            df = normalize_import_dataframe(pd.read_csv(uploaded_file))
            with st.spinner("Importing — please wait..."):
                result = import_sources_and_destinations(df, expected_source_type)
            if result["ok"]:
                st.success("Import completed successfully")
                st.divider()
                col_records, col_sources, col_destinations, col_multi_source = st.columns(4)
                col_records.metric(
                    label="Records (Mappings)",
                    value=result["total_records"],
                    help="Total number of source-to-destination mapping records created.",
                )
                col_sources.metric(
                    label="Distinct Sources",
                    value=result["total_sources"],
                    help="Number of unique source objects imported.",
                )
                col_destinations.metric(
                    label="Distinct Destinations",
                    value=result["total_destinations"],
                    help="Number of unique destination tables imported.",
                )
                col_multi_source.metric(
                    label="Multi-Source Destinations",
                    value=result["multi_source_destinations"],
                    help="Destinations that have more than one distinct source mapped to them.",
                )
            else:
                st.error("Import failed")
                st.json(result)
