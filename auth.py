import streamlit as st
import os
import time
from supabase import create_client
from dotenv import load_dotenv
import ingest_shopify  # This imports your data fetching script

# 1. Load Secrets
load_dotenv("secrets.txt")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def login_form():
    """Handles Login and Registration logic"""
    st.header("🔒 Login to GrowifyX")
    
    # Input field for Shop URL
    shop_url = st.text_input("Enter your Shop URL (e.g., 5h1azi-yh.myshopify.com)")
    
    # --- LOGIN SECTION ---
    col1, col2 = st.columns(2)
    
    if col1.button("Login / Connect"):
        if shop_url:
            try:
                # Check if this shop exists in our DB
                response = supabase.table("shops").select("*").eq("shop_url", shop_url).execute()
                
                if response.data:
                    # User exists! Log them in.
                    st.success(f"✅ Welcome back, {shop_url}!")
                    st.session_state["logged_in"] = True
                    st.session_state["shop_url"] = shop_url
                    st.session_state["access_token"] = response.data[0]["access_token"]
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⚠️ Store not found. Please Register below.")
            except Exception as e:
                st.error(f"Database Error: {e}")

    # --- REGISTRATION SECTION ---
    st.divider()
    st.subheader("New Store? Register Here")
    token = st.text_input("Enter Access Token (from secrets.txt)", type="password")
    
    if st.button("🚀 Register & Initialize"):
        if shop_url and token:
            try:
                # 1. Save User to Database
                data = {"shop_url": shop_url, "access_token": token}
                supabase.table("shops").upsert(data).execute()
                
                # 2. TRIGGER IMMEDIATE DATA SYNC ⚡
                # This calls the function in ingest_shopify.py to get real data now
                with st.spinner("⏳ Connecting to Shopify & Fetching Orders..."):
                    # We pass the supabase client so the script can save data
                    ingest_shopify.fetch_orders(shop_url, token, supabase)
                
                # 3. Auto-Login after success
                st.success("✅ Registration Successful! Logging you in...")
                st.session_state["logged_in"] = True
                st.session_state["shop_url"] = shop_url
                st.session_state["access_token"] = token
                
                time.sleep(1)
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Registration Failed: {e}")
        else:
            st.error("Please fill in both Shop URL and Token.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["shop_url"] = None
    st.session_state["access_token"] = None
    st.rerun()