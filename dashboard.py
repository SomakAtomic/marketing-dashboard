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
    # --- CHANGED: Now reads from a .csv file instead of .xlsx ---
    try:
        df_excel = pd.read_csv("raw_data.csv")
    except FileNotFoundError:
        st.error("Error: The historical data file 'raw_data.csv' was not found.")
        df_excel = pd.DataFrame()

    try:
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        # --- CHANGED: Update the sheet name and tab name ---
        # Replace "YOUR_NEW_GOOGLE_SHEET_NAME" with the actual name of your new Google Sheet file
        spreadsheet = gc.open("Vets Version-2.0")
        worksheet = spreadsheet.worksheet("Raw Data-Combined")
        
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
# The rest of the file remains exactly the same...
# -----------------------------------------------------------------------------
# 4. SIDEBAR AND FILTERS
st.sidebar.image("logo.png", use_container_width=True) 
st.sidebar.header("Dashboard Filters")
# ... (rest of the code is unchanged)