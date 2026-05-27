import streamlit as st
from streamlit_agraph import Config, Edge, Node, agraph

from app.services.db import (
    list_cluster_names,
    list_database_names,
    list_destination_cluster_names,
    list_destination_server_names,
    list_destination_table_names,
    list_destinations,
    list_mapping_objects,
    list_schema_names,
    list_server_names,
    list_source_types,
    list_sources,
)

st.set_page_config(page_title="Data Mapping Metadata Editor", layout="wide")
st.title("Existing Mapping Graph")
st.caption(
    "Read-only visualisation of existing source-to-destination mappings for analysis. "
    "Orphan nodes are hidden when filters are active."
)

# ── Source filters ──────────────────────────────────────────────────────────
st.subheader("Source filters")

_source_types = list_source_types()
if not _source_types:
    st.info("No source metadata found. Import CSV first.")
    st.stop()

_col_type, _ = st.columns([3, 5])
with _col_type:
    source_type = st.radio(
        "Source type",
        options=[None, *_source_types],
        format_func=lambda v: "All" if v is None else v,
        horizontal=True,
        help="Filter by source type. 'All' includes every source type.",
    )

# Show server/database/schema filters for postgres and for "All" (None).
# Hide them when kafka is explicitly selected since kafka sources lack those fields.
_show_pg_filters = source_type != "kafka"

if _show_pg_filters:
    _col_sc_cluster, _col_sc_server, _col_sc_database, _col_sc_schema = st.columns(4)
else:
    _col_sc_cluster, _, _, _ = st.columns(4)

_src_cluster_names = list_cluster_names(source_type)
with _col_sc_cluster:
    src_cluster = st.selectbox(
        "Cluster",
        options=[None, *_src_cluster_names],
        format_func=lambda v: "All" if v is None else v,
        key="src_cluster",
        help="Filter sources by cluster.",
    )

if _show_pg_filters:
    _src_server_names = list_server_names(source_type, src_cluster)
    with _col_sc_server:
        src_server = st.selectbox(
            "Server",
            options=[None, *_src_server_names],
            format_func=lambda v: "All" if v is None else v,
            key="src_server",
            help="Filter sources by server.",
        )

    _src_database_names = list_database_names(source_type, src_cluster, src_server)
    with _col_sc_database:
        src_database = st.selectbox(
            "Database",
            options=[None, *_src_database_names],
            format_func=lambda v: "All" if v is None else v,
            key="src_database",
            help="Filter sources by database.",
        )

    _src_schema_names = list_schema_names(source_type, src_cluster, src_server, src_database)
    with _col_sc_schema:
        src_schema = st.selectbox(
            "Schema",
            options=[None, *_src_schema_names],
            format_func=lambda v: "All" if v is None else v,
            key="src_schema",
            help="Filter sources by PostgreSQL schema.",
        )
else:
    src_server = None
    src_database = None
    src_schema = None

# ── Destination filters ─────────────────────────────────────────────────────
st.subheader("Destination filters")

_col_dst_cluster, _col_dst_server, _col_dst_table, _ = st.columns(4)

_dst_cluster_names = list_destination_cluster_names()
with _col_dst_cluster:
    dst_cluster = st.selectbox(
        "Cluster",
        options=[None, *_dst_cluster_names],
        format_func=lambda v: "All" if v is None else v,
        key="dst_cluster",
        help="Filter destinations by cluster.",
    )

_dst_server_names = list_destination_server_names(dst_cluster)
with _col_dst_server:
    dst_server = st.selectbox(
        "Server",
        options=[None, *_dst_server_names],
        format_func=lambda v: "All" if v is None else v,
        key="dst_server",
        help="Filter destinations by server.",
    )

_dst_table_names = list_destination_table_names(dst_cluster, dst_server)
with _col_dst_table:
    dst_table = st.selectbox(
        "Table",
        options=[None, *_dst_table_names],
        format_func=lambda v: "All" if v is None else v,
        key="dst_table",
        help="Filter destinations by table name.",
    )

# ── Cross-filter: keep only mappings where both sides pass their filters ────
filtered_sources = list_sources(source_type, src_cluster, src_server, src_database, src_schema)
filtered_dests = list_destinations(dst_cluster, dst_server, dst_table)

filtered_src_ids = {s.id for s in filtered_sources}
filtered_dst_ids = {d.id for d in filtered_dests}

all_mappings = list_mapping_objects()
visible_mappings = [
    m for m in all_mappings
    if m.source_id in filtered_src_ids and m.destination_id in filtered_dst_ids
]

if not visible_mappings:
    st.info("No mappings match the current filters.")
    st.stop()

# Restrict to nodes that actually appear in visible mappings (drop orphans)
visible_src_ids = {m.source_id for m in visible_mappings}
visible_dst_ids = {m.destination_id for m in visible_mappings}

src_by_id = {s.id: s for s in filtered_sources if s.id in visible_src_ids}
dst_by_id = {d.id: d for d in filtered_dests if d.id in visible_dst_ids}


# ── Build interactive graph (vis.js via streamlit-agraph) ─────────────────
def _source_label(s) -> str:
    if s.source_type == "kafka":
        parts = [p for p in [s.cluster_name, s.topic] if p]
    else:
        parts = [p for p in [s.server, s.database, s.pg_schema, s.table_name] if p]
    return "\n".join(parts) if parts else f"source_{s.id}"


def _dest_label(d) -> str:
    parts = [p for p in [d.cluster_name, d.server, d.database, d.table_name] if p]
    return "\n".join(parts) if parts else f"dest_{d.id}"


# Assign a distinct colour to each source cluster and each destination cluster.
# Two separate palettes keep source and destination clusters visually distinct
# even when both sides share the same cluster name.
_SRC_PALETTE = ["#5DADE2", "#48C9B0", "#52BE80", "#AF7AC5", "#5499C7", "#45B39D"]
_DST_PALETTE = ["#F5B041", "#EC7063", "#A569BD", "#DC7633", "#F0B27A", "#E59866"]

_src_clusters = sorted({s.cluster_name or "" for s in src_by_id.values()})
_dst_clusters = sorted({d.cluster_name or "" for d in dst_by_id.values()})

_src_cluster_color = {
    c: _SRC_PALETTE[i % len(_SRC_PALETTE)] for i, c in enumerate(_src_clusters)
}
_dst_cluster_color = {
    c: _DST_PALETTE[i % len(_DST_PALETTE)] for i, c in enumerate(_dst_clusters)
}

graph_nodes: list[Node] = []
graph_edges: list[Edge] = []

for _src in sorted(src_by_id.values(), key=lambda s: s.id):
    _cluster = _src.cluster_name or ""
    _color = _src_cluster_color.get(_cluster, "#D7DBDD")
    _tooltip = "\n".join(filter(None, [
        f"Type: {_src.source_type}",
        f"Cluster: {_cluster}" if _cluster else None,
        f"Server: {_src.server}" if _src.server else None,
        f"Database: {_src.database}" if _src.database else None,
        f"Schema: {_src.pg_schema}" if _src.pg_schema else None,
        f"Table: {_src.table_name}" if _src.table_name else None,
        f"Topic: {_src.topic}" if _src.topic else None,
    ]))
    graph_nodes.append(Node(
        id=f"src_{_src.id}",
        label=_source_label(_src),
        size=18,
        shape="box",
        color=_color,
        title=_tooltip,
    ))

for _dst in sorted(dst_by_id.values(), key=lambda d: d.id):
    _cluster = _dst.cluster_name or ""
    _color = _dst_cluster_color.get(_cluster, "#FAD7A0")
    _tooltip = "\n".join(filter(None, [
        f"Cluster: {_cluster}" if _cluster else None,
        f"Server: {_dst.server}" if _dst.server else None,
        f"Database: {_dst.database}" if _dst.database else None,
        f"Table: {_dst.table_name}",
    ]))
    graph_nodes.append(Node(
        id=f"dst_{_dst.id}",
        label=_dest_label(_dst),
        size=18,
        shape="box",
        color=_color,
        title=_tooltip,
    ))

for m in visible_mappings:
    graph_edges.append(Edge(
        source=f"src_{m.source_id}",
        target=f"dst_{m.destination_id}",
    ))

_config = Config(
    width="100%",
    height=650,
    directed=True,
    physics=True,
    hierarchical=False,
)

# ── Render ──────────────────────────────────────────────────────────────────
st.subheader("Graph")
st.caption(
    "Drag nodes to rearrange. Scroll to zoom. Hover over a node for details."
)
agraph(nodes=graph_nodes, edges=graph_edges, config=_config)

# Colour legend
def _swatch(color: str, label: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;margin-right:12px;">'
        f'<span style="display:inline-block;width:13px;height:13px;background:{color};'
        f'border-radius:2px;margin-right:4px;"></span>{label}</span>'
    )

_legend_html = (
    '<div style="font-size:0.85rem;margin-top:6px;">'
    "<strong>Sources</strong>&nbsp;"
    + "".join(_swatch(c, k or "(no cluster)") for k, c in _src_cluster_color.items())
    + "&nbsp;&nbsp;<strong>Destinations</strong>&nbsp;"
    + "".join(_swatch(c, k or "(no cluster)") for k, c in _dst_cluster_color.items())
    + "</div>"
)
st.markdown(_legend_html, unsafe_allow_html=True)

st.caption(
    f"Showing {len(src_by_id)} source(s) \u2192 {len(dst_by_id)} destination(s) "
    f"across {len(visible_mappings)} mapping(s)."
)
