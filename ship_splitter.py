import streamlit as st
import pandas as pd
import math
from io import StringIO

st.set_page_config(layout="wide")
st.title("🚀 EVE Online Ship Splitter")
st.write("Split your ship inventory into balanced packages based on volume, with limited stack splitting and consolidated output.")

# 🎛️ Sidebar configuration
st.sidebar.header("⚙️ Packing Settings")

# Max volume per package (already in main area, optional to move here)
volume_limit = st.sidebar.number_input(
    "📦 Max Volume per Package (m³)",
    min_value=100_000,
    max_value=1_250_000,
    value=350_000,
    step=50_000
)

# Heuristic weight sliders (0.0 to 1.0), internally scaled
alpha_ui = st.sidebar.slider("📦 Volume Fit Weight (α)", 0.0, 1.0, 1.0, 0.05)
beta_ui = st.sidebar.slider("💰 Value Balance Weight (β)", 0.0, 1.0, 0.2, 0.01)

# Convert to actual internal weights
alpha = alpha_ui
beta = beta_ui * 1e-8  # scale β so it’s meaningful vs α

# Max stack splits
max_splits = st.sidebar.slider("🔪 Max Stack Splits", 1, 10, 3)


# 📋 Input area for TSV
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

# 📥 Parse and validate input
try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception as e:
    st.error("❌ Could not parse TSV input.")
    st.stop()

# 💥 Split stacks with max 3 splits, respecting volume & value limits
MAX_SPLITS = max_splits
MAX_STACK_VALUE = 5_000_000_000
expanded_rows = []

for _, row in df.iterrows():
    count = int(row["Count"])
    value = float(row["Value"])
    volume = float(row["Volume"])
    ship_type = row["Type"]

    max_units_by_value = MAX_STACK_VALUE // value if value > 0 else count
    max_units_by_volume = volume_limit // volume if volume > 0 else count

    # Max chunk size by constraints
    chunk_size_limit = int(min(max_units_by_value or count, max_units_by_volume or count))

    # Calculate needed splits
    needed_splits = math.ceil(count / chunk_size_limit) if chunk_size_limit > 0 else 1

    # Limit to max 3 splits
    splits = min(needed_splits, MAX_SPLITS)

    # Evenly distribute counts
    base_chunk_size = count // splits
    remainder = count % splits

    for i in range(splits):
        current_chunk = base_chunk_size + (1 if i < remainder else 0)
        expanded_rows.append({
            "Type": ship_type,
            "Count": current_chunk,
            "Volume": volume,
            "Value": value
        })

df = pd.DataFrame(expanded_rows)

# 📊 Derived columns
df["TotalVolume"] = df["Volume"] * df["Count"]
df["TotalValue"] = df["Value"] * df["Count"]
total_volume = df["TotalVolume"].sum()
total_value = df["TotalValue"].sum()
estimated_packages = math.ceil(total_volume / volume_limit)

st.markdown(f"📦 **Estimated Packages Needed**: {estimated_packages}")
st.markdown(f"📊 **Total Volume**: {total_volume:,.0f} m³")
st.markdown(f"💰 **Total Value**: {total_value:,.0f} ISK")

# 📦 Multi-objective bin packing: prefer tight volume fit + value balancing
def pack_items_multi_objective(df_expanded, volume_limit, alpha=alpha, beta=beta):
    """
    Multi-objective heuristic packing:
    - alpha: weight for remaining volume (prefer tighter volume fit)
    - beta: weight for value balancing (prefer lower total ISK value)
    """
    items = df_expanded.sort_values(by="ValueDensity", ascending=False).to_dict(orient="records")
    packages = []

    for item in items:
        best_fit_idx = -1
        best_score = float('inf')

        for i, pkg in enumerate(packages):
            space_left = volume_limit - pkg['total_volume']
            if space_left >= item['TotalVolume']:
                score = alpha * space_left + beta * pkg['total_value']
                if score < best_score:
                    best_fit_idx = i
                    best_score = score

        if best_fit_idx == -1:
            packages.append({
                'types': [item],
                'total_value': item['TotalValue'],
                'total_volume': item['TotalVolume']
            })
        else:
            pkg = packages[best_fit_idx]
            pkg['types'].append(item)
            pkg['total_value'] += item['TotalValue']
            pkg['total_volume'] += item['TotalVolume']

    return packages

# 🧠 Add ValueDensity column
df["ValueDensity"] = df["Value"] / df["Volume"]

# 📦 Run the multi-objective packer
packages = pack_items_multi_objective(df, volume_limit, alpha=alpha, beta=beta)

# Consolidation function to group same ship types in a package
def consolidate_package(package):
    df_pkg = pd.DataFrame(package['types'])
    grouped = df_pkg.groupby('Type').agg({
        'Count': 'sum',
        'Volume': 'first',  # per-unit volume
        'Value': 'first'    # per-unit value
    }).reset_index()
    grouped['TotalVolume'] = grouped['Count'] * grouped['Volume']
    grouped['TotalValue'] = grouped['Count'] * grouped['Value']
    return grouped

# 🪟 Show results in columns
left_col, right_col = st.columns([3, 2])

with left_col:
    for i, package in enumerate(packages, 1):
        st.subheader(f"📦 Package {i}")
        st.write(f"**Total Volume**: {package['total_volume']:,} m³")
        st.write(f"**Total Value**: {package['total_value']:,} ISK")

        consolidated_df = consolidate_package(package)
        st.dataframe(consolidated_df)

with right_col:
    st.subheader("📊 Summary View")
    summary_rows = []
    for i, package in enumerate(packages, 1):
        consolidated_df = consolidate_package(package)
        summary_rows.append({
            "Package": f"Package {i}",
            "Total Volume (m³)": package['total_volume'],
            "Total Value (ISK)": package['total_value'],
            "Ship Types": len(consolidated_df),
            "Total Ships": consolidated_df["Count"].sum()
        })
    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df.style.format({
        "Total Volume (m³)": "{:,.0f}",
        "Total Value (ISK)": "{:,.0f}"
    }))
