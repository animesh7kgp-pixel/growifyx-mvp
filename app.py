import streamlit as st
import pandas as pd
import os
from supabase import create_client
from dotenv import load_dotenv
import auth  # Import the auth file we just made

# 1. Page Config
st.set_page_config(page_title="GrowifyX Dashboard", layout="wide")

# 2. Check Login State
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- STATE 1: NOT LOGGED IN ---
if not st.session_state["logged_in"]:
    auth.login_form()
    st.stop()  # Stop the code here. Don't show the dashboard.

# --- STATE 2: LOGGED IN (The Dashboard) ---
# Load Secrets
load_dotenv("secrets.txt")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sidebar with Logout
with st.sidebar:
    st.write(f"Connected: **{st.session_state['shop_url']}**")
    if st.button("Logout"):
        auth.logout()

st.title("🚀 GrowifyX: Marketing Intelligence")

# 3. Fetch Data for THIS SPECIFIC SHOP
@st.cache_data
def get_data(shop_url):
    # Notice we filter by 'shop_url' (or user_id) here!
    # For now, we pull all data because your tables don't have a 'shop_url' column yet.
    # We will add that column next.
    
    orders_response = supabase.table("shopify_orders").select("*").execute()
    ads_response = supabase.table("facebook_ads").select("*").execute()
    
    return pd.DataFrame(orders_response.data), pd.DataFrame(ads_response.data)

try:
    orders_df, ads_df = get_data(st.session_state["shop_url"])

    # (Everything below is the same visualization logic as before)
    # Convert dates
    orders_df['date'] = pd.to_datetime(orders_df['date'])
    ads_df['date'] = pd.to_datetime(ads_df['date'])

    # Group by Date
    daily_sales = orders_df.groupby('date')['amount'].sum().reset_index()
    daily_spend = ads_df.groupby('date')['spend'].sum().reset_index()

    # Merge
    df = pd.merge(daily_sales, daily_spend, on='date', how='outer').fillna(0)
    df = df.sort_values('date')
    df['ROAS'] = df['amount'] / df['spend']

    # KPIs
    col1, col2, col3 = st.columns(3)
    total_sales = df['amount'].sum()
    total_spend = df['spend'].sum()
    total_roas = total_sales / total_spend if total_spend > 0 else 0

    col1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
    col2.metric("💸 Ad Spend", f"₹{total_spend:,.0f}")
    col3.metric("📈 Overall ROAS", f"{total_roas:.2f}x")

    st.divider()
    st.subheader("Sales vs. Ad Spend")
    st.line_chart(df.set_index('date')[['amount', 'spend']], color=["#00CC96", "#EF553B"])

except Exception as e:
    st.error(f"Error loading data: {e}")