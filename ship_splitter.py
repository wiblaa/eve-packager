import streamlit as st
import pandas as pd
import math
from io import StringIO
from collections import defaultdict

st.set_page_config(layout="wide")
st.title("🚀 Ship Splitter with Soft Stack Split Limit")

# --- Configurable inputs ---
volume_limit = st.number_input("📦 Max Volume per Package (m³)", 100_000, 1_250_000, 350_000, 50_000)
value_limit = st.number_input("💰 Max ISK per Package", 1_000_000_000, 50_000_000_000, 10_000_000_000, 500_000_000)
soft_split_limit = st.slider("🪓 Soft Max Splits per Ship Type", 1, 10, 3)

# --- TSV Input ---
tsv_input = st.text_area("📋 Paste TSV (Type, Count, Volume, Value)", height=300)
if not tsv_input.strip():
    st.stop()

try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception:
    st.error("Invalid TSV format. Please include Type, Count, Volume, Value.")
    st.stop()

# --- Preprocessing with enforced per-stack ISK limit (max 50% of value_limit) ---
rows = []
split_counts = defaultdict(int)
for _, r in df.iterrows():
    count = int(r["Count"])
    unit_vol = float(r["Volume"])
    unit_val = float(r["Value"])
    type_name = r["Type"]

    max_stack_value = value_limit / 2
    max_units_by_isk = math.floor(max_stack_value / unit_val)
    max_units_by_vol = math.floor(volume_limit / unit_vol)
    chunk_size = max(1, min(max_units_by_isk, max_units_by_vol))

    for i in range(math.ceil(count / chunk_size)):
        actual_count = chunk_size if i < math.ceil(count / chunk_size) - 1 else count - chunk_size * (math.ceil(count / chunk_size) - 1)
        split_counts[type_name] += 1
        rows.append({
            "Type": type_name,
            "Count": actual_count,
            "Volume": unit_vol,
            "Value": unit_val,
            "TotalVolume": actual_count * unit_vol,
            "TotalValue": actual_count * unit_val
        })

# --- Apply soft penalty to types that exceed the soft split limit ---
def penalty_key(item):
    splits = split_counts[item["Type"]]
    penalty = max(0, splits - soft_split_limit)
    return -item["TotalVolume"] / (1 + 0.1 * penalty)  # penalize over-split types slightly

rows.sort(key=penalty_key)

# --- Modified First-Fit Decreasing with ISK & Volume limits ---
bins = []
for item in rows:
    placed = False
    for b in bins:
        used_vol = sum(i["TotalVolume"] for i in b)
        used_val = sum(i["TotalValue"] for i in b)
        if used_vol + item["TotalVolume"] <= volume_limit and used_val + item["TotalValue"] <= value_limit:
            b.append(item)
            placed = True
            break
    if not placed:
        bins.append([item])

# --- Consolidate per package ---
def consolidate(bin_items):
    dfp = pd.DataFrame(bin_items)
    grouped = dfp.groupby("Type").agg({
        "Count": "sum",
        "Volume": "first",
        "Value": "first"
    }).reset_index()
    grouped["TotalVolume"] = grouped["Count"] * grouped["Volume"]
    grouped["TotalValue"] = grouped["Count"] * grouped["Value"]
    return grouped

# --- UI Display ---
left, right = st.columns([3, 2])

with left:
    for i, b in enumerate(bins, 1):
        consolidated = consolidate(b)
        st.subheader(f"📦 Package {i}")
        st.write(f"**Volume**: {consolidated.TotalVolume.sum():,.0f} m³")
        st.write(f"**Value**: {consolidated.TotalValue.sum():,.0f} ISK")
        st.dataframe(consolidated)

with right:
    st.subheader("📊 Summary")
    summary = []
    for i, b in enumerate(bins, 1):
        s = consolidate(b)
        summary.append({
            "Package": i,
            "Volume (m³)": s.TotalVolume.sum(),
            "Value (ISK)": s.TotalValue.sum(),
            "Ship Types": len(s),
            "Total Ships": s["Count"].sum()
        })
    st.dataframe(pd.DataFrame(summary).style.format({
        "Volume (m³)": "{:,.0f}",
        "Value (ISK)": "{:,.0f}"
    }), use_container_width=True)
