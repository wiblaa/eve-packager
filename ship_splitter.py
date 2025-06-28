import streamlit as st
import pandas as pd
import math
from io import StringIO

st.title("🚀 EVE Online Ship Splitter")
st.write("Split your ship inventory into balanced packages based on volume and ISK value.")

# 📦 Volume limit per package (user-configurable)
volume_limit = st.number_input(
    "📦 Max Volume per Package (m³)",
    min_value=100_000,
    max_value=1_250_000,
    value=350_000,
    step=50_000
)

# 📋 Tab-separated ship list input
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

# Load and validate input
try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception as e:
    st.error("❌ Could not parse TSV input.")
    st.stop()

# 💥 Split stacks with total value > 5B ISK
MAX_STACK_VALUE = 5_000_000_000
expanded_rows = []

for _, row in df.iterrows():
    count = int(row["Count"])
    value = float(row["Value"])
    volume = float(row["Volume"])
    ship_type = row["Type"]
    max_units = MAX_STACK_VALUE // value

    if count * value > MAX_STACK_VALUE and max_units > 0:
        while count > max_units:
            expanded_rows.append({
                "Type": ship_type,
                "Count": int(max_units),
                "Volume": volume,
                "Value": value
            })
            count -= max_units
        if count > 0:
            expanded_rows.append({
                "Type": ship_type,
                "Count": int(count),
                "Volume": volume,
                "Value": value
            })
    else:
        expanded_rows.append({
            "Type": ship_type,
            "Count": count,
            "Volume": volume,
            "Value": value
        })

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

# 🧠 Apply First-Fit Decreasing algorithm
items = df.sort_values(by="TotalVolume", ascending=False).to_dict(orient="records")
packages = []

for item in items:
    placed = False
    for pkg in packages:
        if pkg['total_volume'] + item['TotalVolume'] <= volume_limit:
            pkg['types'].append(item)
            pkg['total_value'] += item['TotalValue']
            pkg['total_volume'] += item['TotalVolume']
            placed = True
            break

    if not placed:
        packages.append({
            'types': [item],
            'total_value': item['TotalValue'],
            'total_volume': item['TotalVolume']
        })

# 📊 Display results in two columns
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
