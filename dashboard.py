# -----------------------------------------------------------------------------
# 1. IMPORT LIBRARIES
# -----------------------------------------------------------------------------
import streamlit as st
import pandas as pd
from datetime import datetime, date
import gspread 

# -----------------------------------------------------------------------------
# 2. PAGE SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BFP Marketing Dashboard",
    page_icon="🐾",
    layout="wide"
)
st.title("🐾 BFP Marketing Performance Dashboard")

# -----------------------------------------------------------------------------
# 3. DATA LOADING AND CLEANING
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600) # Refresh data every hour
def get_combined_data():
    try:
        df_excel = pd.read_excel("raw_data.xlsx")
    except FileNotFoundError:
        st.error("Error: The historical data file 'raw_data.xlsx' was not found.")
        df_excel = pd.DataFrame()

    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        worksheet = gc.open("Vets Raw").sheet1
        data = worksheet.get_all_records()
        df_gsheet = pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")
        df_gsheet = pd.DataFrame()

    if not df_excel.empty and not df_gsheet.empty:
        df_combined = pd.concat([df_excel, df_gsheet], ignore_index=True)
    elif not df_excel.empty:
        df_combined = df_excel
    else:
        df_combined = df_gsheet

    if df_combined.empty:
        st.error("No data loaded. Please check your data sources.")
        st.stop()
        
    numeric_cols = ['Impressions', 'Clicks', 'Cost', 'Conversions', 'GA-Booking', 'Year']
    for col in numeric_cols:
        df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce').fillna(0)
    
    df_combined['Date'] = pd.to_datetime(df_combined['Date'], errors='coerce')
    df_combined.dropna(subset=['Date'], inplace=True)
    
    return df_combined

df = get_combined_data()

# -----------------------------------------------------------------------------
# 4. SIDEBAR AND FILTERS
# -----------------------------------------------------------------------------
st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.header("Dashboard Filters")

channel_options = ["All"] + sorted(df["Channel"].unique().tolist())
channel = st.sidebar.selectbox("Select Channel", options=channel_options)

# --- NEW: Logic for Searchable Campaign Filter ---

# First, get the base list of campaigns depending on the channel
if channel == "All":
    base_campaign_list = sorted(df["Campaign"].unique().tolist())
else:
    base_campaign_list = sorted(df[df["Channel"] == channel]["Campaign"].unique().tolist())

# Add a text input for the search term
campaign_search = st.sidebar.text_input("Search Campaign Name")

# Filter the list based on the search term
if campaign_search:
    # Use list comprehension to find campaigns that contain the search term (case-insensitive)
    filtered_campaigns = [c for c in base_campaign_list if campaign_search.lower() in c.lower()]
    campaign_options = ["All"] + filtered_campaigns
else:
    campaign_options = ["All"] + base_campaign_list

# Display the dropdown with the (potentially filtered) list of campaigns
campaign = st.sidebar.selectbox("Select Campaign", options=campaign_options)
# --- End of new search logic ---


st.sidebar.markdown("---")
st.sidebar.subheader("Main Period")
date_range = st.sidebar.date_input("Select Date Range", value=(df["Date"].min(), df["Date"].max()), min_value=df["Date"].min(), max_value=df["Date"].max())

compare_enabled = st.sidebar.checkbox("Compare Date", value=True)
compare_date_range = None
if compare_enabled:
    st.sidebar.subheader("Comparison Period")
    compare_date_range = st.sidebar.date_input("Select Comparison Date Range", value=(df["Date"].min(), df["Date"].max()), min_value=df["Date"].min(), max_value=df["Date"].max())

# -----------------------------------------------------------------------------
# 5. DATA PROCESSING & KPI CALCULATION
# -----------------------------------------------------------------------------
def calculate_kpis(dataframe):
    cost = dataframe["Cost"].sum()
    bookings = dataframe["GA-Booking"].sum()
    cpb = cost / bookings if bookings > 0 else 0
    return {"Cost": cost, "Booking": bookings, "CPB": cpb}

def calculate_summary_kpis(grouped_df):
    summary = grouped_df.sum()
    summary['CTR'] = summary['Clicks'] / summary['Impressions'] if summary['Impressions'].sum() > 0 else 0
    summary['CPC'] = summary['Cost'] / summary['Clicks'] if summary['Clicks'].sum() > 0 else 0
    summary['CPB'] = summary['Cost'] / summary['GA-Booking'] if summary['GA-Booking'].sum() > 0 else 0
    summary['CVR'] = summary['Conversions'] / summary['Clicks'] if summary['Clicks'].sum() > 0 else 0
    return summary

base_mask = df['Date'].notna() 
if channel != "All":
    base_mask = base_mask & (df["Channel"] == channel)
if campaign != "All":
    base_mask = base_mask & (df["Campaign"] == campaign)

df_main = pd.DataFrame() 
if len(date_range) == 2:
    main_start, main_end = date_range
    main_mask = base_mask & (df["Date"] >= pd.to_datetime(main_start)) & (df["Date"] <= pd.to_datetime(main_end))
    df_main = df[main_mask]
    
    kpis_main_total = calculate_kpis(df_main) 

    kpis_compare_total = {"Cost": 0, "Booking": 0, "CPB": 0} 
    df_compare = pd.DataFrame() 
    if compare_enabled and compare_date_range and len(compare_date_range) == 2:
        compare_start, compare_end = compare_date_range
        compare_mask = base_mask & (df["Date"] >= pd.to_datetime(compare_start)) & (df["Date"] <= pd.to_datetime(compare_end))
        df_compare = df[compare_mask]
        kpis_compare_total = calculate_kpis(df_compare)

today = pd.Timestamp.now().date() 
start_of_year = date(today.year, 1, 1)
start_of_month = date(today.year, today.month, 1)
start_of_week = today - pd.to_timedelta(today.weekday(), unit='d')

df_ytd = df[df['Date'].dt.date >= start_of_year]
df_mtd = df[df['Date'].dt.date >= start_of_month]
df_wtd = df[df['Date'].dt.date >= start_of_week]

kpis_ytd = calculate_kpis(df_ytd)
kpis_mtd = calculate_kpis(df_mtd)
kpis_wtd = calculate_kpis(df_wtd)

# -----------------------------------------------------------------------------
# 6. DISPLAY DASHBOARD SECTIONS IN ORDER
# -----------------------------------------------------------------------------

# --- SECTION 1: CUSTOM PERIOD ANALYSIS ---
st.header("Custom Period Analysis")
if not df_main.empty:
    st.subheader("Period vs. Comparison")
    comp_col1, comp_col2, comp_col3 = st.columns(3)
    delta_cost = kpis_main_total["Cost"] - kpis_compare_total["Cost"]
    delta_booking = kpis_main_total["Booking"] - kpis_compare_total["Booking"]
    delta_cpb = kpis_main_total["CPB"] - kpis_compare_total["CPB"]
    
    comp_col1.metric("COST", f"${kpis_main_total['Cost']:,.2f}", f"${delta_cost:,.2f}" if compare_enabled else None)
    comp_col2.metric("BOOKING", f"{kpis_main_total['Booking']:,}", f"{delta_booking:,}" if compare_enabled else None)
    comp_col3.metric("CPB", f"${kpis_main_total['CPB']:,.2f}", f"${delta_cpb:,.2f}" if compare_enabled else None, delta_color="inverse")
else:
    st.warning("No data found for the selected 'Main Period' and filters.")

st.markdown("---")

# --- SECTION 2: PERFORMANCE AT-A-GLANCE ---
st.header("Performance At-a-Glance")
st.markdown("""<style> .kpi-box { background-color: #f8f9fa; border: 1px solid #000; border-radius: 5px; padding: 20px; text-align: center; color: #000; margin-bottom: 10px; height: 120px; display: flex; flex-direction: column; justify-content: center; } .kpi-box h3 { margin: 0 0 5px 0; font-size: 1.2em; font-weight: bold; } .kpi-box p { margin: 0; font-size: 1.8em; font-weight: bold; } .yellow-box { background-color: #FFF3C4; } .purple-box { background-color: #E6E0F8; } .green-box  { background-color: #D5F5E3; } .blue-box   { background-color: #D6EAF8; } </style>""", unsafe_allow_html=True)
periods = { "WTD": kpis_wtd, "MTD": kpis_mtd, "YTD": kpis_ytd }
for period_name, kpi_data in periods.items():
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f'<div class="kpi-box yellow-box"><h3>{period_name}</h3></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="kpi-box purple-box"><h3>COST</h3><p>${kpi_data["Cost"]:,.0f}</p></div>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="kpi-box green-box"><h3>BOOKING</h3><p>{kpi_data["Booking"]:,}</p></div>', unsafe_allow_html=True)
    with col4: st.markdown(f'<div class="kpi-box blue-box"><h3>CPB</h3><p>${kpi_data["CPB"]:,.0f}</p></div>', unsafe_allow_html=True)

st.markdown("---")

# --- SECTION 3: STATE PERFORMANCE ---
st.header("State Performance")
if not df_main.empty:
    summary_main = df_main.groupby("Region")[['Impressions', 'Clicks', 'Cost', 'Conversions', 'GA-Booking']].apply(calculate_summary_kpis)
    summary_compare = None
    if compare_enabled and not df_compare.empty:
        summary_compare = df_compare.groupby("Region")[['Impressions', 'Clicks', 'Cost', 'Conversions', 'GA-Booking']].apply(calculate_summary_kpis)

    regions_to_display = [
        'New South Wales', 'Victoria', 'Western Australia', 'Queensland', 'Tasmania',
        'South Australia', 'Australian Capital Territory', 'Auckland', 'Wellington',
        "Hawke's Bay", 'Tasman', 'Waikato', 'Manawatu-Whanganui', 'Otago',
        'Nelson', 'Bay of Plenty', 'Canterbury'
    ]
    summary_main = summary_main[summary_main.index.isin(regions_to_display)]
    if summary_compare is not None:
        summary_compare = summary_compare[summary_compare.index.isin(regions_to_display)]

    def get_change_color(value, metric_name):
        increase_is_good = ['Impressions', 'Clicks', 'Cost', 'GA-Booking', 'CTR', 'CVR']
        decrease_is_good = ['CPC', 'CPB']
        if value == 0: return "color: grey;"
        if metric_name in increase_is_good:
            return "color: #00A36C;" if value > 0 else "color: #D32F2F;"
        elif metric_name in decrease_is_good:
            return "color: #00A36C;" if value < 0 else "color: #D32F2F;"
        return "color: grey;" 

    def generate_html_table(main_data, compare_data=None):
        metrics = ['Impressions', 'Clicks', 'Cost', 'GA-Booking', 'CTR', 'CPC', 'CPB', 'CVR']
        html = """<style> .styled-table { border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; } .styled-table th, .styled-table td { border: 1px solid #ddd; padding: 8px; } .styled-table th { padding-top: 12px; padding-bottom: 12px; text-align: center; background-color: #008080; color: white; font-weight: bold; } .styled-table td { text-align: center; } .state-name { text-align: left; font-weight: bold; } .metric-values { font-size: 1em; } .percent-change { font-size: 0.9em; font-weight: bold; } </style><table class="styled-table"> <tr><th>State</th>"""
        for metric in metrics: html += f"<th>{metric.replace('_', ' ')}</th>"
        html += "</tr>"
        for region, main_row in main_data.iterrows():
            html += f"<tr><td class='state-name'>{region}</td>"
            for metric in metrics:
                main_val = main_row.get(metric, 0)
                if metric in ['CTR', 'CVR']: main_val_str = f"{main_val:.2%}"
                elif metric in ['CPC', 'CPB', 'Cost']: main_val_str = f"${main_val:,.2f}"
                else: main_val_str = f"{main_val:,.0f}"
                if compare_data is not None and region in compare_data.index:
                    compare_row = compare_data.loc[region]
                    compare_val = compare_row.get(metric, 0)
                    if metric in ['CTR', 'CVR']: compare_val_str = f"{compare_val:.2%}"
                    elif metric in ['CPC', 'CPB', 'Cost']: compare_val_str = f"${compare_val:,.2f}"
                    else: compare_val_str = f"{compare_val:,.0f}"
                    if compare_val > 0: percent_change = (main_val - compare_val) / compare_val
                    else: percent_change = 0 if main_val == 0 else 1.0
                    color = get_change_color(percent_change, metric)
                    html += f"<td><div class='metric-values'>{main_val_str} | {compare_val_str}</div><div class='percent-change' style='{color}'>{percent_change:.0%}</div></td>"
                else:
                    html += f"<td><div class='metric-values'>{main_val_str}</div></td>"
            html += "</tr>"
        html += "</table>"
        return html

    if compare_enabled and summary_compare is not None:
        html_table = generate_html_table(summary_main, summary_compare)
    else:
        html_table = generate_html_table(summary_main)
    st.markdown(html_table, unsafe_allow_html=True)
else:
     st.warning("No data found for the selected 'Main Period' and filters to display State Performance.")