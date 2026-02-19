import streamlit as st
import pandas as pd
import os
from supabase import create_client
from dotenv import load_dotenv
import auth

# --- NEW GOOGLE GEMINI IMPORTS ---
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List, Literal
import json

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

# Initialize Google Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- AI INSTRUCTION MODELS ---
class RecommendedAction(BaseModel):
    action_type: Literal["kill_ad", "scale_ad", "draft_email", "launch_promo"] = Field(
        description="The specific type of action the user should take."
    )
    confidence_score: int = Field(
        description="Confidence score from 1-100 on how effective this action will be."
    )
    rationale: str = Field(
        description="One sentence explaining WHY this action is recommended."
    )
    target_entity: str = Field(
        description="The ID or name of the ad/product this action applies to (e.g., 'FB Ad Campaign' or 'Shopify Store')."
    )

class InsightResponse(BaseModel):
    summary: str = Field(
        description="A brutal, honest 2-sentence summary of the last 7 days of performance."
    )
    primary_bottleneck: str = Field(
        description="Identify the biggest point of friction (e.g., 'High Ad Spend', 'Low Sales')."
    )
    recommendations: List[RecommendedAction] = Field(
        description="List of 1-3 specific actions the user should take right now."
    )

# Sidebar with Logout
with st.sidebar:
    st.write(f"Connected: **{st.session_state['shop_url']}**")
    if st.button("Logout"):
        auth.logout()

st.title("🚀 GrowifyX: Command Center")

# 3. Fetch Data for THIS SPECIFIC SHOP
@st.cache_data
def get_data(shop_url):
    # Fetch orders and ads from Supabase
    orders_response = supabase.table("shopify_orders").select("*").execute()
    ads_response = supabase.table("facebook_ads").select("*").execute()
    
    return pd.DataFrame(orders_response.data), pd.DataFrame(ads_response.data)

try:
    orders_df, ads_df = get_data(st.session_state["shop_url"])

    # Convert dates
    orders_df['date'] = pd.to_datetime(orders_df['date'])
    ads_df['date'] = pd.to_datetime(ads_df['date'])

    # Group by Date
    daily_sales = orders_df.groupby('date')['amount'].sum().reset_index()
    daily_spend = ads_df.groupby('date')['spend'].sum().reset_index()

    # Merge tables
    df = pd.merge(daily_sales, daily_spend, on='date', how='outer').fillna(0)
    df = df.sort_values('date')
    df['ROAS'] = df['amount'] / df['spend']

    # --- LAYOUT SPLIT: 70% Dashboard, 30% AI Advisor ---
    col_main, col_ai = st.columns([7, 3])

    with col_main:
        # KPIs
        kpi1, kpi2, kpi3 = st.columns(3)
        total_sales = df['amount'].sum()
        total_spend = df['spend'].sum()
        total_roas = total_sales / total_spend if total_spend > 0 else 0

        kpi1.metric("💰 Total Sales", f"₹{total_sales:,.0f}")
        kpi2.metric("💸 Ad Spend", f"₹{total_spend:,.0f}")
        kpi3.metric("📈 Overall ROAS", f"{total_roas:.2f}x")

        st.divider()
        st.subheader("Sales vs. Ad Spend")
        st.line_chart(df.set_index('date')[['amount', 'spend']], color=["#00CC96", "#EF553B"])

    with col_ai:
        st.subheader("🧠 AI Strategist")
        st.caption("Your automated growth teammate.")
        
        if st.button("Run Data Analysis 🚀", use_container_width=True):
            with st.spinner("Analyzing your data for free..."):
                try:
                    # 1. Turn your DataFrame into a string format the AI can read
                    data_string = df.tail(7).to_string(index=False) 
                    
                    # 2. Setup the Prompt
                    system_prompt = """
                    You are a ruthless, highly-paid D2C Growth Consultant.
                    You analyze combined Shopify and Meta Ads data.
                    Your goal is to find where the brand is bleeding money and where they are missing opportunities.
                    Be extremely concise. Do not use corporate jargon.
                    """
                    user_prompt = f"Here is the data for the last 7 days:\n\n{data_string}\n\nDiagnose the performance and give me exact recommendations."

                    # 3. Call Gemini API
                    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
                    
                    response = model.generate_content(
                        user_prompt,
                        generation_config=genai.GenerationConfig(
                            response_mime_type="application/json",
                            response_schema=InsightResponse,
                            temperature=0.2,
                        )
                    )
                    
                    # 4. Parse the strict JSON back into our Pydantic model
                    insights = InsightResponse.model_validate_json(response.text)

                    # 5. Display the Results
                    st.success("Analysis Complete!")
                    
                    with st.container(border=True):
                        st.markdown(f"**Diagnosis:** {insights.summary}")
                        st.error(f"🚨 **Bottleneck:** {insights.primary_bottleneck}")
                    
                    st.divider()
                    st.markdown("**🎯 Recommended Actions:**")
                    
                    for rec in insights.recommendations:
                        with st.container(border=True):
                            # Add color based on the action type
                            action_color = "red" if rec.action_type == "kill_ad" else "green" if rec.action_type == "scale_ad" else "blue"
                            st.markdown(f":{action_color}[**{rec.action_type.replace('_', ' ').upper()}**] - {rec.target_entity}")
                            st.caption(rec.rationale)
                            st.progress(rec.confidence_score / 100, text=f"Confidence: {rec.confidence_score}%")
                            
                            # Add a fake action button for the UI
                            action_text = "Draft Email" if rec.action_type == "draft_email" else "Execute Action"
                            st.button(f"{action_text} →", key=f"btn_{rec.target_entity}")
                            
                except Exception as e:
                    st.error(f"AI Error: Details: {e}")

except Exception as e:
    st.error(f"Waiting for data... ({e})")