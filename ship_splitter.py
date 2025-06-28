import streamlit as st
import pandas as pd
import math
from io import StringIO

st.set_page_config(layout="wide")
st.title("🚀 EVE Online Ship Splitter")
st.write("Split your ship inventory into balanced packages based on volume and value, with limited stack splitting and local improvement steps.")

# --- User inputs ---
volume_limit = st.number_input(
    "📦 Max Volume per Package (m³)",
    min_value=100_000,
    max_value=1_250_000,
    value=350_000,
    step=50_000
)

max_package_value = st.number_input(
    "💰 Max Value per Package (ISK, 0 for no limit)",
    min_value=0,
    max_value=50_000_000_000,
    value=10_000_000_000,
    step=500_000_000
)

max_splits = st.slider(
    "🔪 Max Stack Splits",
    min_value=1,
    max_value=10,
    value=4,
    step=1
)

alpha = st.slider(
    "⚖️ Alpha (value weight)",
    min_value=0.1,
    max_value=5.0,
    value=1.0,
    step=0.01,
    help="Weight for value when sorting and packing."
)

beta = st.slider(
    "⚖️ Beta (volume weight)",
    min_value=0.1,
    max_value=5.0,
    value=0.29,
    step=0.01,
    help="Weight for volume when sorting and packing."
)

# --- Default input data ---
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

# --- Parse input ---
try:
    df = pd.read_csv(StringIO(tsv_input), sep="\t")
    assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
except Exception:
    st.error("❌ Could not parse TSV input. Ensure columns: Type, Count, Volume, Value")
    st.stop()

# --- Expand stacks with limited splitting ---
expanded_rows = []

for _, row in df.iterrows():
    count = int(row["Count"])
    value = float(row["Value"])
    volume = float(row["Volume"])
    ship_type = row["Type"]

    # Calculate max units per chunk by volume and value constraints
    max_units_by_value = max_package_value // value if value > 0 and max_package_value > 0 else count
    max_units_by_volume = volume_limit // volume if volume > 0 else count
    chunk_size_limit = int(min(max_units_by_value or count, max_units_by_volume or count))

    # Ensure chunk_size_limit is at least 1
    chunk_size_limit = max(chunk_size_limit, 1)

    needed_splits = math.ceil(count / chunk_size_limit)
    splits = min(needed_splits, max_splits)

    base_chunk_size = count // splits
    remainder = count % splits

    for i in range(splits):
        current_chunk = base_chunk_size + (1 if i < remainder else 0)
        expanded_rows.append({
            "Type": ship_type,
            "Count": current_chunk,
            "Volume": volume,
            "Value": value,
            "TotalVolume": current_chunk * volume,
            "TotalValue": current_chunk * value
        })

df_expanded = pd.DataFrame(expanded_rows)

# --- Sorting heuristic combining alpha and beta weights ---
df_expanded['Score'] = alpha * df_expanded['TotalValue'] / (df_expanded['TotalVolume'] + 1) + beta * df_expanded['TotalVolume']

items = df_expanded.sort_values(by='Score', ascending=False).to_dict(orient='records')

# --- Packing using First-Fit Decreasing (FFD) ---
packages = []

for item in items:
    placed = False
    for pkg in packages:
        if pkg['total_volume'] + item['TotalVolume'] <= volume_limit and \
           (max_package_value == 0 or pkg['total_value'] + item['TotalValue'] <= max_package_value):
            pkg['types'].append(item)
            pkg['total_volume'] += item['TotalVolume']
            pkg['total_value'] += item['TotalValue']
            placed = True
            break
    if not placed:
        packages.append({
            'types': [item],
            'total_volume': item['TotalVolume'],
            'total_value': item['TotalValue']
        })

# --- Local improvement step (move + swap) ---
def can_move(item, to_pkg, volume_limit, max_value_limit):
    vol_after = to_pkg['total_volume'] + item['TotalVolume']
    val_after = to_pkg['total_value'] + item['TotalValue']
    if vol_after <= volume_limit and (max_value_limit == 0 or val_after <= max_value_limit):
        return True
    return False

def local_improvement(packages, volume_limit, max_value_limit=0, max_iterations=5):
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        # Move single items
        for i in range(len(packages)):
            for j in range(len(packages)):
                if i == j:
                    continue
                pkg_i = packages[i]
                pkg_j = packages[j]

                for item_idx, item in enumerate(pkg_i['types']):
                    if can_move(item, pkg_j, volume_limit, max_value_limit):
                        leftover_before = (volume_limit - pkg_i['total_volume']) + (volume_limit - pkg_j['total_volume'])
                        leftover_after = (volume_limit - (pkg_i['total_volume'] - item['TotalVolume'])) + (volume_limit - (pkg_j['total_volume'] + item['TotalVolume']))

                        if leftover_after < leftover_before:
                            # Move item
                            pkg_j['types'].append(item)
                            pkg_j['total_volume'] += item['TotalVolume']
                            pkg_j['total_value'] += item['TotalValue']

                            del pkg_i['types'][item_idx]
                            pkg_i['total_volume'] -= item['TotalVolume']
                            pkg_i['total_value'] -= item['TotalValue']

                            improved = True
                            break
                if improved:
                    break
            if improved:
                break

        if improved:
            continue

        # Try swapping items
        for i in range(len(packages)):
            for j in range(i+1, len(packages)):
                pkg_i = packages[i]
                pkg_j = packages[j]

                for idx_i, item_i in enumerate(pkg_i['types']):
                    for idx_j, item_j in enumerate(pkg_j['types']):
                        vol_i_after = pkg_i['total_volume'] - item_i['TotalVolume'] + item_j['TotalVolume']
                        vol_j_after = pkg_j['total_volume'] - item_j['TotalVolume'] + item_i['TotalVolume']
                        val_i_after = pkg_i['total_value'] - item_i['TotalValue'] + item_j['TotalValue']
                        val_j_after = pkg_j['total_value'] - item_j['TotalValue'] + item_i['TotalValue']

                        if (vol_i_after <= volume_limit and vol_j_after <= volume_limit and
                            (max_value_limit == 0 or (val_i_after <= max_value_limit and val_j_after <= max_value_limit))):

                            leftover_before = (volume_limit - pkg_i['total_volume']) + (volume_limit - pkg_j['total_volume'])
                            leftover_after = (volume_limit - vol_i_after) + (volume_limit - vol_j_after)

                            if leftover_after < leftover_before:
                                # Swap
                                pkg_i['types'][idx_i], pkg_j['types'][idx_j] = item_j, item_i
                                pkg_i['total_volume'] = vol_i_after
                                pkg_j['total_volume'] = vol_j_after
                                pkg_i['total_value'] = val_i_after
                                pkg_j['total_value'] = val_j_after

                                improved = True
                                break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break

    # Remove empty packages
    packages[:] = [pkg for pkg in packages if pkg['types']]
    return packages

packages = local_improvement(packages, volume_limit, max_package_value, max_iterations=10)

# --- Consolidate package entries ---
def consolidate_package(package):
    df_pkg = pd.DataFrame(package['types'])
    grouped = df_pkg.groupby('Type').agg({
        'Count': 'sum',
        'Volume': 'first',
        'Value': 'first'
    }).reset_index()
    grouped['TotalVolume'] = grouped['Count'] * grouped['Volume']
    grouped['TotalValue'] = grouped['Count'] * grouped['Value']
    return grouped

# --- Summary and UI output ---
total_volume = sum(pkg['total_volume'] for pkg in packages)
total_value = sum(pkg['total_value'] for pkg in packages)
estimated_packages = len(packages)

st.markdown(f"📦 **Estimated Packages Needed**: {estimated_packages}")
st.markdown(f"📊 **Total Volume**: {total_volume:,.0f} m³")
st.markdown(f"💰 **Total Value**: {total_value:,.0f} ISK")

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
