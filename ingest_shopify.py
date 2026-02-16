import requests
from supabase import create_client
import os

# We don't load .env here anymore because we get keys dynamically!

def fetch_orders(shop_url, access_token, supabase_client):
    """
    Fetches orders for a SPECIFIC shop and saves them to Supabase.
    """
    print(f"⏳ Fetching orders for {shop_url}...")
    
    # 1. API Request to Shopify
    url = f"https://{shop_url}/admin/api/2024-01/orders.json?status=any"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Error fetching from Shopify: {response.text}")
        return False

    data = response.json()
    orders = data.get("orders", [])
    print(f"✅ Found {len(orders)} orders!")

    # 2. Save to Supabase (Tagging them with shop_url)
    formatted_orders = []
    for order in orders:
        formatted_orders.append({
            "order_id": str(order["id"]),
            "shop_url": shop_url,  # IMPORTANT: We tag the data with the shop name!
            "date": order["created_at"].split("T")[0],
            "amount": float(order["total_price"]),
            "currency": order["currency"],
            "customer_email": order.get("email", "Unknown")
        })
        
    if formatted_orders:
        try:
            # Upsert (Insert or Update)
            supabase_client.table("shopify_orders").upsert(formatted_orders).execute()
            print("   Saved to Database!")
            return True
        except Exception as e:
            print(f"   ⚠️ Database Error: {e}")
            return False
    
    return True