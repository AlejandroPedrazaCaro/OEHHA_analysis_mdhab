# app.py
# The dashboard page. Start it with:  streamlit run app.py
# Streamlit runs this file from top to bottom every time the page opens,
# so the data is downloaded fresh each time.

import altair as alt   # chart library; it comes installed with Streamlit
import pandas as pd
import streamlit as st

import data   # our own file, data.py

# Chart colors. The red is kept for exceedances only.
LINE_COLOR = "#8a8a85"        # neutral gray, readable on light and dark backgrounds
EXCEEDANCE_COLOR = "#d03b3b"  # red

# Space (in pixels) reserved for the y-axis labels on both charts. Using the
# same number on both makes their plot areas start at the same place, so the
# dates line up vertically.
Y_AXIS_WIDTH = 60

# ---------------------------------------------------------------
# Page title
# ---------------------------------------------------------------
st.set_page_config(page_title="Scripps Pier HAB Dashboard")
st.title("Lingulodinium polyedra at Scripps Pier")

# ---------------------------------------------------------------
# Section 0: load and prepare the data (all the work is in data.py)
# ---------------------------------------------------------------
try:
    df = data.load_data()
except Exception as error:
    # If the download fails (no internet, server down), show the reason and stop.
    st.error(f"Could not download data from ERDDAP: {error}")
    st.stop()

recent = data.last_five_years(df)
threshold, used_fallback = data.compute_threshold(recent)
recent = data.flag_exceedances(recent, threshold)

# ---------------------------------------------------------------
# Section 1: status card
# ---------------------------------------------------------------

# Only rows that have a cell count (NaN rows are "not counted yet").
counted = recent.dropna(subset=["Lingulodinium_polyedra"])

# The last counted row. The table is sorted oldest first, so the last row is the newest.
latest = counted.iloc[-1]

# Samples newer than the latest counted one. All of them are NaN (not counted yet).
pending = recent[recent["time"] > latest["time"]]

# st.container(border=True) draws a box around everything inside the "with" block.
with st.container(border=True):
    st.subheader("Latest counted sample")

    # :red[...] and :green[...] are Streamlit's way to color text.
    if latest["exceeds"]:
        status = ":red[**ABOVE threshold**]"
    else:
        status = ":green[**below threshold**]"

    # f"..." puts values inside the text. {:,.0f} means: comma separators, no decimals.
    st.markdown(f"**{latest['time']:%Y-%m-%d}**: {latest['Lingulodinium_polyedra']:,.0f} cells/L, {status}")
    st.markdown(f"Threshold: {threshold:,.0f} cells/L ({data.THRESHOLD_PERCENTILE}th percentile of the last {data.YEARS} years)")

    # Say how many newer samples are still waiting to be counted, if any.
    if len(pending) > 0:
        st.caption(f"{len(pending)} newer sample(s) not counted yet. Most recent sample date: {recent['time'].max():%Y-%m-%d}")

# Short note if the threshold had to use only the samples with cells > 0.
if used_fallback:
    st.info(f"Note: the {data.THRESHOLD_PERCENTILE}th percentile of all counted samples was 0, so the threshold uses only samples with cells > 0.")

# ---------------------------------------------------------------
# Section 2: cell count chart
# ---------------------------------------------------------------
st.subheader("Cell counts")

# The counted samples that are above the threshold.
exceedances = counted[counted["exceeds"]]

# What the hover box shows. format=",.0f" means: comma separators, no decimals.
tooltip = [
    alt.Tooltip("time:T", title="Date", format="%Y-%m-%d"),
    alt.Tooltip("Lingulodinium_polyedra:Q", title="cells/L", format=",.0f"),
    alt.Tooltip("Temp:Q", title="Temp (°C)"),
]

# The date range of both charts: the whole 5-year window, including the
# newest samples that are not counted yet. Using the same range on both
# charts keeps their dates lined up. isoformat() turns a date into text
# like "2026-10-05T18:52:00+00:00", which the chart library understands.
date_range = [recent["time"].min().isoformat(), recent["time"].max().isoformat()]

# The x and y settings that the line and the dots share.
# ":T" means "a time", ":Q" means "a number" (quantitative).
x = alt.X("time:T", title="Sample date", scale=alt.Scale(domain=date_range))
# format=",.0f" shows 350,000 instead of 3.5e+5.
y = alt.Y("Lingulodinium_polyedra:Q", title="cells/L", axis=alt.Axis(format=",.0f", minExtent=Y_AXIS_WIDTH))

# Layer 1: gray line through all counted samples.
# strokeJoin="round" rounds the corners. With sharp corners, the line pokes
# past the data point at every spike (for example, below 0).
line = alt.Chart(counted).mark_line(color=LINE_COLOR, strokeWidth=2, strokeJoin="round").encode(x=x, y=y)

# Layer 2: invisible dots on every sample. They give the mouse
# something to hover over, so every sample shows its tooltip.
hover_dots = alt.Chart(counted).mark_point(size=150, opacity=0, clip=True).encode(x=x, y=y, tooltip=tooltip)

# Layer 3: red dots on the exceedances.
red_dots = alt.Chart(exceedances).mark_point(
    color=EXCEEDANCE_COLOR, filled=True, size=70
).encode(x=x, y=y, tooltip=tooltip)

# Layer 4: dashed horizontal line at the threshold.
# It needs a tiny table of its own with one row: the threshold value.
# Its y uses the same title and number format as the other layers,
# because all the layers share one y axis.
threshold_table = pd.DataFrame({"threshold": [threshold]})
threshold_y = alt.Y("threshold:Q", title="cells/L", axis=alt.Axis(format=",.0f", minExtent=Y_AXIS_WIDTH))
threshold_line = alt.Chart(threshold_table).mark_rule(
    color=EXCEEDANCE_COLOR, strokeDash=[6, 4]
).encode(y=threshold_y)

# "+" stacks the layers on top of each other, in this order.
cells_chart = line + hover_dots + red_dots + threshold_line
st.altair_chart(cells_chart)

st.caption(f"Dashed red line: threshold ({threshold:,.0f} cells/L). Red dots: {len(exceedances)} samples above it. Samples that were not counted are left out of this chart.")

# ---------------------------------------------------------------
# Section 3: water temperature chart
# ---------------------------------------------------------------
st.subheader("Water temperature")

# Rows that have a temperature. This includes the newest samples
# whose cells are not counted yet, because their temperature is known.
temps = recent.dropna(subset=["Temp"])

# zero=False lets the axis start near the lowest temperature instead of at 0 °C,
# so the ups and downs are visible.
temp_y = alt.Y("Temp:Q", title="°C", scale=alt.Scale(zero=False), axis=alt.Axis(minExtent=Y_AXIS_WIDTH))

# This hover box shows only date and temperature. Some of these rows have no
# cell count, and the comma format would display a missing count as "0".
temp_tooltip = [
    alt.Tooltip("time:T", title="Date", format="%Y-%m-%d"),
    alt.Tooltip("Temp:Q", title="Temp (°C)"),
]

# Same pattern as the cell chart: a line, plus invisible dots for the hover box.
temp_line = alt.Chart(temps).mark_line(color=LINE_COLOR, strokeWidth=2, strokeJoin="round").encode(x=x, y=temp_y)
temp_hover_dots = alt.Chart(temps).mark_point(size=150, opacity=0, clip=True).encode(x=x, y=temp_y, tooltip=temp_tooltip)

# .properties(height=200) makes this chart shorter than the cell chart.
temp_chart = (temp_line + temp_hover_dots).properties(height=200)
st.altair_chart(temp_chart)

# ---------------------------------------------------------------
# Section 4: table of exceedance dates
# ---------------------------------------------------------------
st.subheader("Exceedance dates")

if len(exceedances) == 0:
    st.write(f"No samples above the threshold in the last {data.YEARS} years.")
else:
    # Newest first. ascending=False reverses the date order.
    newest_first = exceedances.sort_values("time", ascending=False)

    # A new table with friendly column names. strftime keeps only the date
    # part of the time, so "2024-11-11 19:18:00+00:00" becomes "2024-11-11".
    table = pd.DataFrame({
        "Date": newest_first["time"].dt.strftime("%Y-%m-%d"),
        "cells/L": newest_first["Lingulodinium_polyedra"],
        "Temp (°C)": newest_first["Temp"],
    })

    st.caption(f"{len(table)} samples above {threshold:,.0f} cells/L in the last {data.YEARS} years, newest first. Click a column name to sort.")

    # hide_index=True hides the row numbers on the left.
    # column_config sets how each number column is displayed:
    # "localized" adds comma separators, "%.1f" shows one decimal.
    st.dataframe(
        table,
        hide_index=True,
        column_config={
            "cells/L": st.column_config.NumberColumn(format="localized"),
            "Temp (°C)": st.column_config.NumberColumn(format="%.1f"),
        },
    )