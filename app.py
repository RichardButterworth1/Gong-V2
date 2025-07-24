import os
import base64
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode         # ← add this line
from flask import Flask, request, redirect, jsonify
from dotenv import load_dotenv

app = Flask(__name__)

# Load Gong OAuth credentials from environment
GONG_CLIENT_ID = os.environ.get("GONG_CLIENT_ID")
GONG_CLIENT_SECRET = os.environ.get("GONG_CLIENT_SECRET")
REDIRECT_URI = "https://<your-app>.onrender.com/callback"  # set this to your Render URL

# In-memory storage for OAuth tokens (in production, store securely)
gong_token = {
    "access_token": None,
    "refresh_token": None,
    "api_base_url": None
}

# 1. OAuth Authorization Endpoint (redirect user to Gong auth page)
@app.route("/auth")
def authorize():
    scopes = "api:calls:read api:users:read"
    params = {
        "client_id":    GONG_CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "scope":         scopes,
        "state":         "xyz123",  # you can generate a random state per request
    }
    auth_url = "https://app.gong.io/oauth2/authorize?" + urlencode(params)
    return redirect(auth_url)

# 2. OAuth Callback Endpoint (exchanges code for tokens)
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    # Prepare Basic auth header with client_id:client_secret
    basic_token = base64.b64encode(f"{GONG_CLIENT_ID}:{GONG_CLIENT_SECRET}".encode()).decode()
    token_url = (
        "https://app.gong.io/oauth2/generate-customer-token"
        f"?grant_type=authorization_code&code={code}"
        f"&client_id={GONG_CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    resp = requests.post(token_url, headers={"Authorization": f"Basic {basic_token}"})
    if resp.status_code != 200:
        return f"Token exchange failed: {resp.text}", 500
    data = resp.json()
    # Store the received tokens and API base URL
    gong_token["access_token"] = data["access_token"]
    gong_token["refresh_token"] = data.get("refresh_token")
    gong_token["api_base_url"] = data["api_base_url_for_customer"]  # e.g. "https://company.api.gong.io"
    return "Gong OAuth successful! You can now use the API."

# Helper: ensure we have a valid access token (refresh if needed)
def get_auth_header():
    # (In a full implementation, check token expiration and use refresh_token if expired)
    if not gong_token["access_token"]:
        return None
    return {"Authorization": f"Bearer {gong_token['access_token']}"}

# 3. API Endpoint: List calls in a date range
@app.route("/calls")
def list_calls():
    headers = get_auth_header()
    if not headers:
        return "Not authorized with Gong", 401
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    # Call Gong API: GET /v2/calls with date filters
    url = f"{gong_token['api_base_url']}/v2/calls?start_date={start_date}&end_date={end_date}"
    resp = requests.get(url, headers=headers)
    return jsonify(resp.json()), resp.status_code

# 4. API Endpoint: Get details of a specific call by ID
@app.route("/calls/<call_id>")
def get_call(call_id):
    headers = get_auth_header()
    if not headers:
        return "Not authorized with Gong", 401
    url = f"{gong_token['api_base_url']}/v2/calls/{call_id}"
    resp = requests.get(url, headers=headers)
    return jsonify(resp.json()), resp.status_code

# 5. API Endpoint: Get transcript of a specific call
@app.route("/calls/<call_id>/transcript")
def get_transcript(call_id):
    headers = get_auth_header()
    if not headers:
        return "Not authorized with Gong", 401
    # Gong's transcript API uses POST with JSON body (we'll call it and return the result)
    url = f"{gong_token['api_base_url']}/v2/calls/transcript"
    payload = {"callIds": [call_id]}  # request transcripts for this call ID
    resp = requests.post(url, json=payload, headers=headers)
    return jsonify(resp.json()), resp.status_code

# (Optional) Additional endpoints for other data, e.g., list users, get deal stats, etc., can be added similarly.
