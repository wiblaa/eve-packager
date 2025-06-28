import streamlit as st
import pandas as pd
import math
from io import StringIO

st.set_page_config(layout="wide")
st.title("🚀 Simplified Ship Packer")

# --- Controls ---
volume_limit = st.number_input("Max Volume per Package (m³)", 100_000, 1_250_000, 350_000, 50_000)
value_limit = st.number_input("Max ISK per Package (0 = no limit)", 0, 50_000_000_000, 10_000_000_000, 500_000_000)
max_splits = st.slider("Soft Max Splits per Stack", 1, 10, 3)

# --- Input Data ---
tsv = st.text_area("Paste TSV: Type, Count, Volume, Value", height=200)

try:
    df = pd.read_csv(StringIO(tsv), sep="\t")
    assert {"Type","Count","Volume","Value"}.issubset(df.columns)
except:
    st.error("Invalid TSV format.")
    st.stop()

# --- Pre-split stacks ---
rows = []
warnings = []
for _, r in df.iterrows():
    c, vpc, ipc = int(r.Count), float(r.Volume), float(r.Value)
    tv = vpc * c
    iv = ipc * c

    # Determine ideal chunk size
    max_by_vol = volume_limit / vpc
    max_by_val = value_limit / ipc if value_limit>0 else max_by_vol
    ideal = int(min(max_by_vol, max_by_val or max_by_vol, c))
    ideal = max(ideal, 1)

    split_cnt = math.ceil(c / ideal)
    if split_cnt > max_splits:
        warnings.append(f"{r.Type} split into {split_cnt} (> {max_splits}).")
    for i in range(split_cnt):
        cnt = ideal if i < split_cnt-1 else c - ideal*(split_cnt-1)
        rows.append({"Type": r.Type, "Count": cnt, "Volume": vpc, "Value": ipc,
                     "TotalVolume": cnt*vpc, "TotalValue": cnt*ipc})

if warnings:
    st.warning("⚠️ Split warnings:\n" + "\n".join(warnings))

pack_items = sorted(rows, key=lambda x: -x["TotalVolume"])

packages = []
current = {"types": [], "total_volume":0, "total_value":0}

for item in pack_items:
    if (current["total_volume"] + item["TotalVolume"] > volume_limit) or \
       (value_limit>0 and current["total_value"] + item["TotalValue"] > value_limit):
        packages.append(current)
        current = {"types": [], "total_volume":0, "total_value":0}

    current["types"].append(item)
    current["total_volume"] += item["TotalVolume"]
    current["total_value"] += item["TotalValue"]

if current["types"]:
    packages.append(current)

# --- Display ---
def consolidate(pkg):
    dfp = pd.DataFrame(pkg["types"])
    g = dfp.groupby("Type").agg({"Count":"sum","Volume":"first","Value":"first"})
    g["TotalVolume"] = g.Count*g.Volume
    g["TotalValue"] = g.Count*g.Value
    return g.reset_index()

st.subheader(f"Generated {len(packages)} packages")
cols = st.columns([3,2])

with cols[0]:
    for i, pkg in enumerate(packages,1):
        st.write(f"📦 Package {i}: {pkg['total_volume']} m³, {pkg['total_value']} ISK ({"💥" if pkg['total_value']>value_limit>0 else ""})")
        st.dataframe(consolidate(pkg))

with cols[1]:
    tot_v = sum(p["total_volume"] for p in packages)
    tot_i = sum(p["total_value"] for p in packages)
    st.markdown(f"**Total volume:** {tot_v:,} m³  \n**Total ISK:** {tot_i:,}")

