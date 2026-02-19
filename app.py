import streamlit as st
import pandas as pd
import os
import time
import requests
import json
from supabase import create_client
from dotenv import load_dotenv
import auth

# --- GOOGLE GEMINI IMPORTS ---
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List, Literal

# 1. Page Config
st.set_page_config(page_title="GrowifyX Dashboard", layout="wide")

# 2. Check Login State
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    auth.login_form()
    st.stop()

# Load Secrets
load_dotenv("secrets.txt")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Meta API Keys (Leave blank for Demo Mode)
META_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT = os.getenv("META_AD_ACCOUNT_ID", "")
META_PAGE = os.getenv("META_PAGE_ID", "")

# Initialize Google Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- META API FUNCTIONS ---
META_GRAPH_URL = "https://graph.facebook.com/v18.0"

def deploy_to_meta(headline, primary_text, cta, image_url):
    """Orchestrates the 4-step Meta API sequence."""
    if not META_TOKEN or not META_AD_ACCOUNT:
        # DEMO MODE: Simulate the API call for Loom videos
        time.sleep(1.5)
        st.toast("Uploading Image to Meta...")
        time.sleep(1)
        st.toast("Creating Paused Campaign...")
        time.sleep(1)
        st.toast("Assembling Ad Creative...")
        time.sleep(1.5)
        return "DEMO_SUCCESS"

    # REAL MODE: Actual Meta API Calls
    try:
        # Step 1: Upload Image
        img_bytes = requests.get(image_url).content
        res1 = requests.post(f"{META_GRAPH_URL}/{META_AD_ACCOUNT}/adimages", files={"filename": ("ad.jpg", img_bytes, "image/jpeg")}, data={"access_token": META_TOKEN})
        image_hash = res1.json()["images"][next(iter(res1.json()["images"]))]["hash"]

        # Step 2: Create Campaign
        res2 = requests.post(f"{META_GRAPH_URL}/{META_AD_ACCOUNT}/campaigns", data={"access_token": META_TOKEN, "name": "GrowifyX AI Promo", "objective": "OUTCOME_SALES", "status": "PAUSED", "special_ad_categories": "[]"})
        camp_id = res2.json()["id"]

        # Step 3: Create Ad Set
        targeting = {"geo_locations": {"countries": ["IN", "US"]}, "age_min": 18, "age_max": 65}
        res3 = requests.post(f"{META_GRAPH_URL}/{META_AD_ACCOUNT}/adsets", data={"access_token": META_TOKEN, "name": "AI Broad Audience", "campaign_id": camp_id, "daily_budget": "100000", "billing_event": "IMPRESSIONS", "optimization_goal": "REACH", "targeting": json.dumps(targeting), "status": "PAUSED"})
        adset_id = res3.json()["id"]

        # Step 4: Create Ad
        story_spec = {"page_id": META_PAGE, "link_data": {"image_hash": image_hash, "link": "https://your-d2c-brand.com", "message": primary_text, "name": headline, "call_to_action": {"type": cta}}}
        res4 = requests.post(f"{META_GRAPH_URL}/{META_AD_ACCOUNT}/adcreatives", data={"access_token": META_TOKEN, "name": f"Creative - {headline[:20]}", "object_story_spec": json.dumps(story_spec), "status": "ACTIVE"})
        creative_id = res4.json()["id"]
        
        res5 = requests.post(f"{META_GRAPH_URL}/{META_AD_ACCOUNT}/ads", data={"access_token": META_TOKEN, "name": "GrowifyX AI Drafted Ad", "adset_id": adset_id, "creative": json.dumps({"creative_id": creative_id}), "status": "PAUSED"})
        return res5.json()["id"]
    except Exception as e:
        return f"ERROR: {str(e)}"

# --- AI INSTRUCTION MODELS ---
class AdCreativeDraft(BaseModel):
    headline: str = Field(description="The short, punchy headline.")
    primary_text: str = Field(description="The main body text of the ad.")
    call_to_action: Literal["SHOP_NOW", "LEARN_MORE", "GET_OFFER", "SIGN_UP"] = Field(description="The CTA button text.")
    image_prompt: str = Field(description="Describe the exact image.")

class EmailDraft(BaseModel):
    subject_line: str = Field(description="A high-converting email subject line.")
    body_text: str = Field(description="The full text body of the email.")

class RecommendedAction(BaseModel):
    action_type: Literal["kill_ad", "scale_ad", "draft_email", "launch_promo"] = Field(description="The specific type of action.")
    confidence_score: int = Field(description="Confidence score from 1-100.")
    rationale: str = Field(description="One sentence explaining WHY.")
    target_entity: str = Field(description="The ID or name of the ad/product.")

class InsightResponse(BaseModel):
    summary: str = Field(description="A 2-sentence summary of performance.")
    primary_bottleneck: str = Field(description="Identify the biggest point of friction.")
    recommendations: List[RecommendedAction] = Field(description="List of specific actions.")

# --- AI GENERATION FUNCTIONS ---
@st.cache_data(show_spinner=False)
def generate_ad_draft(action_type, target_entity, rationale):
    system_prompt = "You are an elite D2C performance marketer writing Facebook ads."
    user_prompt = f"Action: {action_type}\nTargeting: {target_entity}\nContext: {rationale}\nWrite exact ad copy."
    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
    res = model.generate_content(user_prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json", response_schema=AdCreativeDraft, temperature=0.7))
    return res.text

@st.cache_data(show_spinner=False)
def generate_email_draft(target_entity, rationale):
    system_prompt = "You are an elite D2C email marketer. Write high-converting retention emails."
    user_prompt = f"Targeting: {target_entity}\nContext: {rationale}\nWrite exact email copy."
    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
    res = model.generate_content(user_prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json", response_schema=EmailDraft, temperature=0.7))
    return res.text

# Sidebar
with st.sidebar:
    st.write(f"Connected: **{st.session_state['shop_url']}**")
    if st.button("Logout"):
        auth.logout()

st.title("🚀 GrowifyX: Command Center")

# Fetch Data
@st.cache_data
def get_data(shop_url):
    orders = supabase.table("shopify_orders").select("*").execute()
    ads = supabase.table("facebook_ads").select("*").execute()
    return pd.DataFrame(orders.data), pd.DataFrame(ads.data)

try:
    orders_df, ads_df = get_data(st.session_state["shop_url"])
    orders_df['date'] = pd.to_datetime(orders_df['date'])
    ads_df['date'] = pd.to_datetime(ads_df['date'])

    daily_sales = orders_df.groupby('date')['amount'].sum().reset_index()
    daily_spend = ads_df.groupby('date')['spend'].sum().reset_index()

    df = pd.merge(daily_sales, daily_spend, on='date', how='outer').fillna(0)
    df = df.sort_values('date')
    
    col_main, col_ai = st.columns([7, 3])

    with col_main:
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
            with st.spinner("Analyzing your data..."):
                try:
                    data_string = df.tail(7).to_string(index=False) 
                    system_prompt = "You are a ruthless D2C Growth Consultant. Analyze Shopify and Meta Ads data. Only recommend from these 4 actions: kill_ad, scale_ad, draft_email, launch_promo."
                    user_prompt = f"Data for last 7 days:\n\n{data_string}\n\nDiagnose and give exact recommendations."

                    model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
                    response = model.generate_content(user_prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json", response_schema=InsightResponse, temperature=0.2))
                    
                    st.session_state["ai_insights"] = response.text
                    st.success("Analysis Complete!")
                except Exception as e:
                    st.error(f"AI Error: {e}")

        # Display Insights
        if "ai_insights" in st.session_state:
            insights = InsightResponse.model_validate_json(st.session_state["ai_insights"])
            
            with st.container(border=True):
                st.markdown(f"**Diagnosis:** {insights.summary}")
                st.error(f"🚨 **Bottleneck:** {insights.primary_bottleneck}")
            
            st.divider()
            st.markdown("**🎯 Recommended Actions:**")
            
            for i, rec in enumerate(insights.recommendations):
                with st.container(border=True):
                    action_color = "red" if rec.action_type == "kill_ad" else "green" if rec.action_type == "scale_ad" else "blue"
                    st.markdown(f":{action_color}[**{rec.action_type.replace('_', ' ').upper()}**] - {rec.target_entity}")
                    st.caption(rec.rationale)
                    
                    if rec.action_type == "draft_email":
                        action_text = "Draft Email"
                    elif rec.action_type == "scale_ad":
                        action_text = "Scale Budget"
                    elif rec.action_type == "kill_ad":
                        action_text = "Pause & Replace Ad"
                    else:
                        action_text = "Draft New Campaign"
                    
                    with st.expander(f"{action_text} →"):
                        if rec.action_type == "kill_ad":
                            st.error(f"⚠️ Pause **{rec.target_entity}** immediately.")
                            st.markdown("### ✨ Replacement Campaign")
                            with st.spinner("Writing replacement ad..."):
                                raw_draft = generate_ad_draft("launch_replacement", rec.target_entity, "Write a fresh ad.")
                                draft = AdCreativeDraft.model_validate_json(raw_draft)
                                
                            edited_primary = st.text_area("Primary Text", value=draft.primary_text, height=100, key=f"repl_text_{i}")
                            img_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?q=80&w=600&auto=format&fit=crop"
                            st.image(img_url, caption=f"AI Vision: {draft.image_prompt}")
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                edited_headline = st.text_input("Headline", value=draft.headline, key=f"repl_head_{i}")
                            with col2:
                                st.button(draft.call_to_action.replace("_", " "), disabled=True, key=f"repl_cta_{i}")
                                
                            st.divider()
                            if st.button("🔴 Pause Old & ✅ Deploy Replacement to Meta", type="primary", key=f"swap_{i}"):
                                with st.spinner("Connecting to Meta Ads Manager..."):
                                    result = deploy_to_meta(edited_headline, edited_primary, draft.call_to_action, img_url)
                                    if "ERROR" in result:
                                        st.error(result)
                                    else:
                                        st.success("✅ Success! New campaign is PAUSED in Meta Ads Manager.")
                                        st.balloons()

                        elif rec.action_type == "scale_ad":
                            st.info("Let's increase the daily budget.")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.text_input("Current Daily Budget", value="₹1,500", disabled=True, key=f"cur_budg_{i}")
                            with col2:
                                new_budget = st.text_input("New Daily Budget", value="₹2,500", key=f"new_budg_{i}")
                            if st.button("🚀 Confirm Budget Increase", type="primary", key=f"boost_{i}"):
                                st.success(f"Budget scaled to {new_budget}!")
                        
                        elif rec.action_type == "draft_email":
                            with st.spinner("Writing email..."):
                                raw_draft = generate_email_draft(rec.target_entity, rec.rationale)
                                draft = EmailDraft.model_validate_json(raw_draft)
                            st.markdown("### 📧 Email Preview")
                            st.text_input("Subject Line", value=draft.subject_line, key=f"subj_{i}")
                            st.text_area("Email Body", value=draft.body_text, height=150, key=f"body_{i}")
                            if st.button("✅ Push to Klaviyo", type="primary", key=f"send_{i}"):
                                st.success("Email Synced Successfully!")

                        elif rec.action_type == "launch_promo": 
                            with st.spinner("Writing ad copy..."):
                                raw_draft = generate_ad_draft(rec.action_type, rec.target_entity, rec.rationale)
                                draft = AdCreativeDraft.model_validate_json(raw_draft)
                            st.markdown("### 📱 Meta Ad Preview")
                            edited_primary = st.text_area("Primary Text", value=draft.primary_text, height=100, key=f"text_{i}")
                            img_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?q=80&w=600&auto=format&fit=crop"
                            st.image(img_url, caption=f"AI Vision: {draft.image_prompt}")
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                edited_headline = st.text_input("Headline", value=draft.headline, key=f"head_{i}")
                            with col2:
                                st.button(draft.call_to_action.replace("_", " "), disabled=True, key=f"cta_{i}")
                            
                            st.divider()
                            if st.button("✅ Deploy to Meta Ads Manager", type="primary", key=f"pub_{i}"):
                                with st.spinner("Connecting to Meta Ads Manager..."):
                                    result = deploy_to_meta(edited_headline, edited_primary, draft.call_to_action, img_url)
                                    if "ERROR" in result:
                                        st.error(result)
                                    else:
                                        st.success("✅ Success! Campaign is created and PAUSED in Meta Ads Manager.")
                                        st.balloons()

except Exception as e:
    st.error(f"Waiting for data... ({e})")