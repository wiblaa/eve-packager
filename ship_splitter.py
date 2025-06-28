import streamlit as st
import pandas as pd
import math
from io import StringIO

st.title("Package Splitter with Balanced Value")

# Inputs
tsv_input = st.text_area("Paste tab-separated ship data (Type, Count, Volume, Value):", height=300)
volume_limit = st.number_input(
    "Package volume limit (m³):",
    min_value=100000,
    max_value=1250000,
    value=350000,
    step=50000
)

MAX_STACK_VALUE = 5_000_000_000
MAX_SPLITS = 3

def split_stacks(df, volume_limit, max_stack_value=MAX_STACK_VALUE, max_splits=MAX_SPLITS):
    expanded_rows = []
    for _, row in df.iterrows():
        count = int(row["Count"])
        value = float(row["Value"])
        volume = float(row["Volume"])
        ship_type = row["Type"]

        max_units_by_value = max_stack_value // value if value > 0 else count
        max_units_by_volume = volume_limit // volume if volume > 0 else count

        chunk_size_limit = int(min(max_units_by_value or count, max_units_by_volume or count))
        splits = min(math.ceil(count / chunk_size_limit) if chunk_size_limit > 0 else 1, max_splits)

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

    df_expanded = pd.DataFrame(expanded_rows)
    df_expanded["TotalVolume"] = df_expanded["Volume"] * df_expanded["Count"]
    df_expanded["TotalValue"] = df_expanded["Value"] * df_expanded["Count"]
    df_expanded["ValueDensity"] = df_expanded["Value"] / df_expanded["Volume"]

    return df_expanded

def pack_items(df_expanded, volume_limit):
    items = df_expanded.sort_values(by="ValueDensity", ascending=False).to_dict(orient="records")
    packages = []

    for item in items:
        best_fit_idx = -1
        min_total_value = float('inf')

        for i, pkg in enumerate(packages):
            space_left = volume_limit - pkg['total_volume']
            if space_left >= item['TotalVolume']:
                if pkg['total_value'] < min_total_value:
                    best_fit_idx = i
                    min_total_value = pkg['total_value']

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

def consolidate_package(pkg):
    # Consolidate identical ship types in a package
    df = pd.DataFrame(pkg['types'])
    grouped = df.groupby('Type').agg({
        'Count': 'sum',
        'Volume': 'first',
        'Value': 'first'
    }).reset_index()
    grouped['TotalVolume'] = grouped['Volume'] * grouped['Count']
    grouped['TotalValue'] = grouped['Value'] * grouped['Count']
    return grouped

if tsv_input.strip():
    try:
        df = pd.read_csv(StringIO(tsv_input), sep="\t")
        assert {"Type", "Count", "Volume", "Value"}.issubset(df.columns)
    except Exception:
        st.error("❌ Could not parse TSV input. Make sure columns Type, Count, Volume, Value exist and data is tab-separated.")
        st.stop()

    df_expanded = split_stacks(df, volume_limit)
    packages = pack_items(df_expanded, volume_limit)

    # Display packages with consolidated rows
    st.header(f"Packages ({len(packages)})")

    cols = st.columns([3, 2])  # left wide for table, right for summary

    with cols[0]:
        for i, pkg in enumerate(packages, 1):
            st.subheader(f"Package {i} - Volume: {pkg['total_volume']:.0f} m³, Value: {pkg['total_value']:.0f} ISK")
            grouped = consolidate_package(pkg)
            st.dataframe(grouped.style.format({
                'Count': '{:.0f}',
                'Volume': '{:.0f}',
                'Value': '{:,.0f}',
                'TotalVolume': '{:.0f}',
                'TotalValue': '{:,.0f}'
            }))

    with cols[1]:
        total_volume_all = sum(pkg['total_volume'] for pkg in packages)
        total_value_all = sum(pkg['total_value'] for pkg in packages)
        avg_volume = total_volume_all / len(packages) if packages else 0
        avg_value = total_value_all / len(packages) if packages else 0

        st.markdown("### Summary")
        st.markdown(f"**Total packages:** {len(packages)}")
        st.markdown(f"**Total volume:** {total_volume_all:,.0f} m³")
        st.markdown(f"**Total value:** {total_value_all:,.0f} ISK")
        st.markdown(f"**Average volume per package:** {avg_volume:,.0f} m³")
        st.markdown(f"**Average value per package:** {avg_value:,.0f} ISK")

else:
    st.info("Please paste your tab-separated ship data above to see package splits.")
