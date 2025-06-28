import streamlit as st # type: ignore
import pandas as pd
import math
from io import StringIO

st.title("🚀 EVE Online Ship Splitter")
st.write("Split your ship inventory into balanced packages based on ISK value and volume.")

# Configurable volume limit
volume_limit = st.number_input(
    "📦 Max Volume per Package (m³)",
    min_value=100_000,
    max_value=1_250_000,
    value=350_000,
    step=50_000
)

# Tab-separated input
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

# Load input
try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception as e:
    st.error("❌ Could not parse TSV input.")
    st.stop()

# Expand large stacks (split those with total value > 5B ISK)
MAX_STACK_VALUE = 5_000_000_000
expanded_rows = []

for _, row in df.iterrows():
    count = row["Count"]
    value = row["Value"]
    volume = row["Volume"]
    max_units = MAX_STACK_VALUE // value

    if count * value > MAX_STACK_VALUE and max_units > 0:
        while count > max_units:
            expanded_rows.append({
                "Type": row["Type"],
                "Count": max_units,
                "Volume": volume,
                "Value": value
            })
            count -= max_units
        if count > 0:
            expanded_rows.append({
                "Type": row["Type"],
                "Count": count,
                "Volume": volume,
                "Value": value
            })
    else:
        expanded_rows.append(row)

df = pd.DataFrame(expanded_rows)


# Derived columns
df["TotalVolume"] = df["Volume"] * df["Count"]
df["TotalValue"] = df["Value"] * df["Count"]

total_volume = df["TotalVolume"].sum()
total_value = df["TotalValue"].sum()

estimated_packages = math.ceil(total_volume / volume_limit)

st.markdown(f"📦 **Estimated Packages Needed**: {estimated_packages}")
st.markdown(f"📊 **Total Volume**: {total_volume:,.0f} m³")
st.markdown(f"💰 **Total Value**: {total_value:,.0f} ISK")

# Sort and initialize packages
df = df.sort_values(by="TotalValue", ascending=False).reset_index(drop=True)
packages = [{'types': [], 'total_value': 0, 'total_volume': 0} for _ in range(estimated_packages)]

# Packing logic
for _, row in df.iterrows():
    count_remaining = row['Count']
    while count_remaining > 0:
        placed = False
        for pkg in sorted(packages, key=lambda p: (p['total_value'], len(p['types']))):
            vol_needed = count_remaining * row['Volume']
            if pkg['total_volume'] + vol_needed <= volume_limit:
                pkg['types'].append({
                    'Type': row['Type'],
                    'Count': count_remaining,
                    'TotalValue': vol_needed * (row['Value'] / row['Volume']),
                    'TotalVolume': vol_needed
                })
                pkg['total_value'] += count_remaining * row['Value']
                pkg['total_volume'] += vol_needed
                count_remaining = 0
                placed = True
                break

        if not placed:
            best_fit = None
            for pkg in packages:
                space_left = volume_limit - pkg['total_volume']
                max_units = space_left // row['Volume']
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
                st.error(f"❌ Cannot fit any units of {row['Type']} due to volume limit.")
                break

# Display package contents and summary
summary_rows = []

# Show content and summary side-by-side
left_col, right_col = st.columns([3, 2])

with left_col:
    for i, package in enumerate(packages, 1):
        st.subheader(f"📦 Package {i}")
        st.write(f"**Total Volume**: {package['total_volume']:,} m³")
        st.write(f"**Total Value**: {package['total_value']:,} ISK")
        contents_df = pd.DataFrame(package['types'])
        st.dataframe(contents_df)

with right_col:
    st.subheader("📊 Summary View")
    summary_rows = []
    for i, package in enumerate(packages, 1):
        contents_df = pd.DataFrame(package['types'])
        summary_rows.append({
            "Package": f"Package {i}",
            "Total Volume (m³)": package['total_volume'],
            "Total Value (ISK)": package['total_value'],
            "Ship Types": len(contents_df),
            "Total Ships": contents_df["Count"].sum()
        })
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df.style.format({
        "Total Volume (m³)": "{:,.0f}",
        "Total Value (ISK)": "{:,.0f}"
    }))

