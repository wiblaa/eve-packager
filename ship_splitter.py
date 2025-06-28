import streamlit as st
import pandas as pd
import math
from io import StringIO

st.set_page_config(layout="wide")
st.title("🚀 Ship Packer with MFFD Algorithm")

# --- Settings ---
volume_limit = st.number_input("📦 Max Volume per Package (m³)", 100_000, 1_250_000, 350_000, 50_000)
value_limit = st.number_input("💰 Max ISK per Package (0 = no limit)", 0, 50_000_000_000, 10_000_000_000, 500_000_000)

# --- Input Data ---
tsv_input = st.text_area("📋 Paste TSV (Type,Count,Volume,Value):", height=300)

try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except:
    st.error("Invalid TSV format. Please include Type, Count, Volume, Value.")
    st.stop()

# --- Split Rows (force no single stack > value_limit / 2) ---
rows = []
for _, r in df.iterrows():
    count = int(r["Count"])
    unit_vol = float(r["Volume"])
    unit_val = float(r["Value"])
    max_val_per_stack = value_limit / 2.5 if value_limit > 0 else float("inf")

    # max units per stack due to ISK limit (hard cap per stack)
    max_units_by_isk = math.floor(max_val_per_stack / unit_val)
    max_units_by_vol = math.floor(volume_limit / unit_vol)

    chunk_size = max(1, min(max_units_by_isk, max_units_by_vol))

    for i in range(math.ceil(count / chunk_size)):
        actual_count = chunk_size if i < math.ceil(count / chunk_size) - 1 else count - chunk_size * (math.ceil(count / chunk_size) - 1)
        rows.append({
            "Type": r["Type"],
            "Count": actual_count,
            "TotalVolume": actual_count * unit_vol,
            "TotalValue": actual_count * unit_val
        })

# --- MFFD Packing ---
rows.sort(key=lambda x: -x["TotalVolume"])
bins = []

for item in rows:
    if item["TotalVolume"] > volume_limit * 0.5:
        bins.append([item])
        continue

    placed = False
    for b in bins:
        used_vol = sum(i["TotalVolume"] for i in b)
        used_val = sum(i["TotalValue"] for i in b)

        if used_vol + item["TotalVolume"] <= volume_limit and (value_limit == 0 or used_val + item["TotalValue"] <= value_limit):
            b.append(item)
            placed = True
            break

    if not placed:
        bins.append([item])

# --- Consolidation ---
def consolidate(bin_items):
    dfp = pd.DataFrame(bin_items)
    grouped = dfp.groupby("Type").agg({"Count": "sum", "TotalVolume": "sum", "TotalValue": "sum"}).reset_index()
    return grouped

# --- Display ---
cols = st.columns([3, 2])

with cols[0]:
    for i, b in enumerate(bins, 1):
        consolidated = consolidate(b)
        st.subheader(f"📦 Package {i} — Vol: {consolidated.TotalVolume.sum():,} / {volume_limit:,} | ISK: {consolidated.TotalValue.sum():,}")
        st.dataframe(consolidated)

with cols[1]:
    st.subheader("📊 Summary")
    summary = []
    for i, b in enumerate(bins, 1):
        s = consolidate(b)
        summary.append({
            "Package": i,
            "Volume": s.TotalVolume.sum(),
            "Value": s.TotalValue.sum(),
            "Ship Types": len(s),
            "Total Ships": s["Count"].sum()
        })
    st.dataframe(pd.DataFrame(summary).style.format({"Volume": "{:,.0f}", "Value": "{:,.0f}"}), use_container_width=True)
