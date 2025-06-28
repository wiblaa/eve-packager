import streamlit as st
import pandas as pd
import math
from io import StringIO

st.title("🚀 EVE Online Ship Splitter")
st.write("Split your ship inventory into balanced packages based on ISK value and volume.")

# User-configurable constraints
volume_limit = st.number_input(
    "📦 Max Volume per Package (m³)",
    min_value=100_000,
    max_value=1_250_000,
    value=350_000,
    step=50_000
)

value_limit = st.number_input(
    "💰 Max Value per Package (ISK)",
    min_value=1_000_000_000,
    value=10_000_000_000,
    step=1_000_000_000
)

# TSV input
default_data = """Type\tCount\tVolume\tValue
Rook\t16\t10000\t3720706652
Vulture\t8\t15000\t3695534158
Bustard\t1\t20000\t221087431
Impel\t16\t20000\t3128286353
Mastodon\t8\t20000\t1552349380
Skiff\t8\t3750\t2311869261
Rapier\t12\t10000\t2472076540
Cerberus\t1\t10000\t204051104
Sacrilege\t25\t10000\t5501283304
Broadsword\t5\t10000\t1361108440
Devoter\t4\t10000\t1139692111
Onyx\t10\t10000\t3310685004
Phobos\t4\t10000\t1040900556
Heretic\t2\t5000\t117449602
Basilisk\t32\t10000\t7656753835"""

tsv_input = st.text_area(
    "📋 Paste your tab-separated ship list (Type, Count, Volume, Value)",
    value=default_data,
    height=300
)

# Load TSV
try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception as e:
    st.error("❌ Could not parse TSV input.")
    st.stop()

# Calculate totals
df["TotalVolume"] = df["Volume"] * df["Count"]
df["TotalValue"] = df["Value"] * df["Count"]

total_volume = df["TotalVolume"].sum()
total_value = df["TotalValue"].sum()

estimated_packages = math.ceil(max(
    total_volume / volume_limit,
    total_value / value_limit
))

st.markdown(f"📦 **Estimated Packages Needed**: {estimated_packages}")
st.markdown(f"📊 **Total Volume**: {total_volume:,.0f} m³")
st.markdown(f"💰 **Total Value**: {total_value:,.0f} ISK")

# Sort by total value
df = df.sort_values(by="TotalValue", ascending=False).reset_index(drop=True)
packages = [{'types': [], 'total_value': 0, 'total_volume': 0} for _ in range(estimated_packages)]

# Packing logic with dual constraints
for _, row in df.iterrows():
    count_remaining = row['Count']
    while count_remaining > 0:
        placed = False
        for pkg in sorted(packages, key=lambda p: (p['total_value'], len(p['types']))):
            vol_needed = count_remaining * row['Volume']
            val_needed = count_remaining * row['Value']
            if (pkg['total_volume'] + vol_needed <= volume_limit and
                pkg['total_value'] + val_needed <= value_limit):
                pkg['types'].append({
                    'Type': row['Type'],
                    'Count': count_remaining,
                    'TotalValue': val_needed,
                    'TotalVolume': vol_needed
                })
                pkg['total_value'] += val_needed
                pkg['total_volume'] += vol_needed
                count_remaining = 0
                placed = True
                break

        if not placed:
            best_fit = None
            for pkg in packages:
                vol_space = volume_limit - pkg['total_volume']
                val_space = value_limit - pkg['total_value']
                max_units_by_volume = vol_space // row['Volume']
                max_units_by_value = val_space // row['Value']
                max_units = min(max_units_by_volume, max_units_by_value)
                if max_units > 0:
                    best_fit = pkg
                    break

            if best_fit:
                best_fit['types'].append({
                    'Type': row['Type'],
                    'Count': max_units,
                    'TotalValue': max_units * row['Value'],
                    'TotalVolume': max_units * row['Volume']
                })
                best_fit['total_value'] += max_units * row['Value']
                best_fit['total_volume'] += max_units * row['Volume']
                count_remaining -= max_units
            else:
                st.error(f"❌ Cannot fit any units of {row['Type']} due to constraints.")
                break

# Display packages and summary
summary_rows = []

for i, package in enumerate(packages, 1):
    st.subheader(f"📦 Package {i}")
    st.write(f"**Total Volume**: {package['total_volume']:,} m³")
    st.write
