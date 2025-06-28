import streamlit as st
import pandas as pd
import math
from io import StringIO

st.set_page_config(layout="wide")
st.title("🚀 EVE Online Ship Packer (Unlimited Splits Mode)")

# --- User Settings ---
volume_limit = st.number_input("📦 Max Volume per Package (m³)", 100_000, 1_250_000, 350_000, 50_000)
value_limit = st.number_input("💰 Max ISK per Package (0 = no limit)", 0, 50_000_000_000, 10_000_000_000, 500_000_000)

# --- Input TSV ---
default_data = """Type\tCount\tVolume\tValue
Broadsword\t5\t10000\t274500000
Cerberus\t10\t10000\t231000000
Curse\t16\t10000\t231800000
Deimos\t20\t10000\t193600000
Devoter\t12\t10000\t307900000
Flycatcher\t40\t5000\t62910000
Guardian\t10\t10000\t185000000
Heretic\t40\t5000\t55940000
Impel\t10\t20000\t200800000
Lachesis\t16\t10000\t188400000
Mastodon\t12\t20000\t204500000
Muninn\t5\t10000\t174900000
Oneiros\t16\t10000\t165900000
Onyx\t32\t10000\t343100000
Phobos\t16\t10000\t268300000
Pontifex\t40\t5000\t53710000
Rapier\t21\t10000\t203700000
Rook\t16\t10000\t228600000
Sacrilege\t20\t10000\t219700000
Scimitar\t16\t10000\t182700000
Skiff\t16\t3750\t281900000
Mackinaw\t24\t3750\t269400000"""

tsv_input = st.text_area("📋 Paste your TSV (Type, Count, Volume, Value)", default_data, height=300)

try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except:
    st.error("❌ Invalid input. Make sure columns are: Type, Count, Volume, Value")
    st.stop()

# --- Split Items as Needed ---
split_rows = []

for _, row in df.iterrows():
    count = int(row["Count"])
    volume = float(row["Volume"])
    value = float(row["Value"])

    max_units_by_volume = volume_limit // volume
    max_units_by_value = value_limit // value if value_limit > 0 else count

    chunk_size = int(min(max_units_by_volume or count, max_units_by_value or count))
    chunk_size = max(chunk_size, 1)

    num_chunks = math.ceil(count / chunk_size)
    for i in range(num_chunks):
        chunk_count = chunk_size if i < num_chunks - 1 else count - chunk_size * (num_chunks - 1)
        split_rows.append({
            "Type": row["Type"],
            "Count": chunk_count,
            "Volume": volume,
            "Value": value,
            "TotalVolume": chunk_count * volume,
            "TotalValue": chunk_count * value
        })

# --- Greedy Packing ---
split_rows.sort(key=lambda x: -x["TotalVolume"])
packages = []
current_pkg = {"types": [], "total_volume": 0, "total_value": 0}

for item in split_rows:
    # If it won't fit, start a new package
    exceeds_volume = current_pkg["total_volume"] + item["TotalVolume"] > volume_limit
    exceeds_value = value_limit > 0 and current_pkg["total_value"] + item["TotalValue"] > value_limit

    if exceeds_volume or exceeds_value:
        packages.append(current_pkg)
        current_pkg = {"types": [], "total_volume": 0, "total_value": 0}

    current_pkg["types"].append(item)
    current_pkg["total_volume"] += item["TotalVolume"]
    current_pkg["total_value"] += item["TotalValue"]

if current_pkg["types"]:
    packages.append(current_pkg)

# --- Consolidate Package Items ---
def consolidate_package(pkg):
    dfp = pd.DataFrame(pkg["types"])
    grouped = dfp.groupby("Type").agg({
        "Count": "sum",
        "Volume": "first",
        "Value": "first"
    }).reset_index()
    grouped["TotalVolume"] = grouped["Count"] * grouped["Volume"]
    grouped["TotalValue"] = grouped["Count"] * grouped["Value"]
    return grouped

# --- Display Results ---
left_col, right_col = st.columns([3, 2])

with left_col:
    for idx, pkg in enumerate(packages, 1):
        st.subheader(f"📦 Package {idx}")
        st.write(f"**Volume**: {pkg['total_volume']:,} m³")
        st.write(f"**Value**: {pkg['total_value']:,} ISK")
        st.dataframe(consolidate_package(pkg), use_container_width=True)

with right_col:
    st.subheader("📊 Summary")
    summary = []
    for idx, pkg in enumerate(packages, 1):
        consolidated = consolidate_package(pkg)
        summary.append({
            "Package": f"Package {idx}",
            "Volume (m³)": pkg["total_volume"],
            "Value (ISK)": pkg["total_value"],
            "Ship Types": len(consolidated),
            "Total Ships": consolidated["Count"].sum()
        })
    st.dataframe(pd.DataFrame(summary).style.format({
        "Volume (m³)": "{:,.0f}",
        "Value (ISK)": "{:,.0f}"
    }), use_container_width=True)
