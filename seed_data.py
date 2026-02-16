import os
import random
import uuid
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Load Secrets
load_dotenv("secrets.txt")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY") # Use Service Role to write freely

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_fake_data():
    print("🌱 Seeding Database with 30 days of Fake Data...")
    
    orders = []
    ads = []
    
    # Loop back 30 days
    today = datetime.now()
    for i in range(30):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        
        # --- Fake Shopify Orders (Randomly 0 to 5 orders per day) ---
        daily_orders_count = random.randint(0, 5)
        for _ in range(daily_orders_count):
            orders.append({
                "order_id": str(uuid.uuid4()),
                "date": date,
                "amount": round(random.uniform(500, 5000), 2), # Sales between ₹500 and ₹5000
                "currency": "INR",
                "customer_email": f"user{random.randint(1,100)}@gmail.com"
            })
            
        # --- Fake Facebook Ads (One entry per day) ---
        ads.append({
            "ad_id": str(uuid.uuid4()),
            "date": date,
            "spend": round(random.uniform(1000, 8000), 2), # Spend between ₹1000 and ₹8000
            "clicks": random.randint(50, 500),
            "impressions": random.randint(1000, 10000)
        })

    # 2. Upload to Supabase
    print(f"📤 Uploading {len(orders)} Orders...")
    supabase.table("shopify_orders").upsert(orders).execute()
    
    print(f"📤 Uploading {len(ads)} Ad Records...")
    supabase.table("facebook_ads").upsert(ads).execute()
    
    print("✅ Done! Your database is now full of data.")

if __name__ == "__main__":
    generate_fake_data()