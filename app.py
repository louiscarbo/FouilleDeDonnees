import streamlit as st
import pandas as pd

st.set_page_config(page_title="Flickr Lyon Map", layout="wide")

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # If your CSV already has taken_dt/upload_dt saved, parse them
    for c in ["taken_dt", "upload_dt"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    # Normalize
    df["tags"] = df["tags"].fillna("").astype(str)
    df["title"] = df["title"].fillna("").astype(str)
    df["url"] = df["url"].fillna("").astype(str)
    return df

st.title("📍 Flickr photos around Lyon — interactive map")

path = st.sidebar.text_input("CSV path", "flickr_data_cleaned.csv")
df = load_data(path)

# --- Sidebar filters
st.sidebar.write("### Filters")

# Top tags list
tags_series = (
    df["tags"].str.lower().str.split(",").explode().str.strip()
)
tags_series = tags_series[tags_series.ne("")]
top_tags = tags_series.value_counts().head(200).index.tolist()

selected_tag = st.sidebar.selectbox("Filter by tag (optional)", ["(no filter)"] + top_tags)

# Date filter (taken_dt)
use_date = "taken_dt" in df.columns
if use_date:
    min_dt = df["taken_dt"].min()
    max_dt = df["taken_dt"].max()
    date_range = st.sidebar.date_input(
        "Taken date range",
        value=(min_dt.date(), max_dt.date()) if pd.notna(min_dt) and pd.notna(max_dt) else None
    )

# Sampling for clickable points
max_points = st.sidebar.slider("Max points to draw (clickable)", 500, 20000, 5000, step=500)

# Map mode
mode = st.sidebar.radio("Map mode", ["Hex (fast overview)", "Points (click + URLs)"])

# --- Apply tag filter
dff = df.copy()
if selected_tag != "(no filter)":
    needle = selected_tag.lower()
    dff = dff[dff["tags"].str.lower().str.contains(rf"(^|,)\s*{needle}\s*(,|$)", regex=True)]

# --- Apply date filter
if use_date and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1)
    dff = dff[(dff["taken_dt"].notna()) & (dff["taken_dt"] >= start) & (dff["taken_dt"] < end)]

st.write(f"Rows after filters: **{len(dff):,}** (from {len(df):,})")

# --- Prepare columns for mapping
# Streamlit expects columns named lat/lon for st.map and pydeck
dff = dff.rename(columns={"long": "lon"}).copy()

# Sample for points mode (clickable)
if len(dff) > max_points:
    dff_points = dff.sample(n=max_points, random_state=0)
else:
    dff_points = dff

# --- Map rendering
if mode == "Hex (fast overview)":
    import pydeck as pdk

    layer = pdk.Layer(
        "HexagonLayer",
        data=dff,
        get_position="[lon, lat]",
        radius=80,          # meters-ish feel (depends on zoom)
        elevation_scale=8,
        elevation_range=[0, 1500],
        pickable=True,
        extruded=True,
    )

    view_state = pdk.ViewState(
        latitude=float(dff["lat"].median()),
        longitude=float(dff["lon"].median()),
        zoom=11,
        pitch=40,
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, map_style=None))

else:
    # Points (clickable tooltips)
    import pydeck as pdk

    # Tooltip shows URL (copy/paste), plus title/tags/date
    tooltip = {
        "html": "<b>{title}</b><br/>{tags}<br/>{taken_dt}<br/><a href='{url}' target='_blank'>Open on Flickr</a>",
        "style": {"backgroundColor": "white", "color": "black"},
    }

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=dff_points,
        get_position="[lon, lat]",
        get_radius=12,
        pickable=True,
        opacity=0.6,
    )

    view_state = pdk.ViewState(
        latitude=float(dff_points["lat"].median()),
        longitude=float(dff_points["lon"].median()),
        zoom=12,
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip, map_style=None))

    st.write("Sample shown below (so you can click the URL easily too):")
    st.dataframe(dff_points[["id", "title", "tags", "taken_dt", "url"]].head(200), use_container_width=True)