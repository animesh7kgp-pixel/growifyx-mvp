import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests

# ==========================================
# 👇 PASTE YOUR DETAILS HERE
# ==========================================
CLIENT_ID = "c44a5b78fab365a4acb18612bb6ca0ea"
API_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET")
SHOP_URL = "5h1azi-yh.myshopify.com" 
# ==========================================

REDIRECT_URI = "http://localhost:3000/callback"
SCOPES = "read_orders,read_analytics"

class TokenHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Shopify calls this function after you login
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            code = params['code'][0]
            print(f"✅ Got Code: {code}")
            
            # 2. We trade the code for the Token
            token_url = f"https://{SHOP_URL}/admin/oauth/access_token"
            payload = {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code
            }
            response = requests.post(token_url, json=payload)
            data = response.json()
            token = data.get('access_token')
            
            if token:
                print("\n" + "="*40)
                print(f"🎉 YOUR SHOPIFY TOKEN IS:\n")
                print(f"{token}")
                print("\n" + "="*40)
                self.wfile.write(b"<h1>Success! Check your VS Code Terminal.</h1>")
                raise KeyboardInterrupt # Stop the script
            else:
                self.wfile.write(b"Error getting token.")
        else:
            self.wfile.write(b"Missing code.")

print("👉 Opening browser...")
# 3. Create the login link
auth_url = (
    f"https://{SHOP_URL}/admin/oauth/authorize?"
    f"client_id={CLIENT_ID}&scope={SCOPES}&"
    f"redirect_uri={REDIRECT_URI}&state=123"
)
webbrowser.open(auth_url)

# 4. Start the server
server = HTTPServer(('localhost', 3000), TokenHandler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("Done.")