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

# --- Split Rows (unlimited splits) ---
rows = []
for _, r in df.iterrows():
    count, vpc, ipc = int(r.Count), float(r.Volume), float(r.Value)
    max_units_vol = volume_limit // vpc
    max_units_val = value_limit // ipc if value_limit>0 else max_units_vol
    chunk = int(min(max_units_vol or count, max_units_val or count))
    chunk = max(chunk, 1)
    for i in range(math.ceil(count / chunk)):
        n = chunk if i < math.ceil(count/chunk)-1 else count - chunk*(math.ceil(count/chunk)-1)
        rows.append({
            "Type": r.Type, "Count":n,
            "TotalVolume": n * vpc,
            "TotalValue": n * ipc
        })

# --- MFFD Packing ---
rows.sort(key=lambda x: -x["TotalVolume"])
bins = []
for item in rows:
    # If item > half capacity → new bin
    if item["TotalVolume"] > volume_limit * 0.5:
        bins.append([item]); continue

    placed = False
    for b in bins:
        used_vol = sum(i["TotalVolume"] for i in b)
        used_val = sum(i["TotalValue"] for i in b)
        if used_vol + item["TotalVolume"] <= volume_limit and (value_limit == 0 or used_val + item["TotalValue"] <= value_limit):
            b.append(item); placed = True; break

    if not placed:
        bins.append([item])

# --- Consolidate and Display ---
def consolidate(bin_items):
    dfp = pd.DataFrame(bin_items)
    g = dfp.groupby("Type").agg({"Count": "sum", "TotalVolume": "sum", "TotalValue":"sum"}).reset_index()
    return g

cols = st.columns([3,2])
with cols[0]:
    for i, b in enumerate(bins,1):
        s = consolidate(b)
        st.subheader(f"📦 Package {i} — Vol: {s.TotalVolume.sum():,} / {volume_limit:,}  |  ISK: {s.TotalValue.sum():,}")
        st.dataframe(s)

with cols[1]:
    summary = []
    for i, b in enumerate(bins,1):
        s = consolidate(b)
        summary.append({
            "Package": i,
            "Volume": s.TotalVolume.sum(),
            "Value": s.TotalValue.sum(),
            "Types": len(s),
            "Ships": s.Count.sum()
        })
    st.dataframe(pd.DataFrame(summary).style.format({"Volume":"{:,}", "Value":"{:,}"}), use_container_width=True)
