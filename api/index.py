import os
import secrets
import string
from datetime import datetime, timezone
from urllib.parse import urlparse, quote, unquote

from flask import Flask, request, jsonify, render_template_string, redirect
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

app = Flask(__name__)

# Config & Environment Variables
MONGODB_URI = "mongodb+srv://maheesharashmi22_db_user:UVjtznEJD5UF3e8x@cluster0.l7gxl3n.mongodb.net"
MONGODB_DATABASE = "mvxymediator"
API_KEY = "mvxyyy"
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "mywebsite.com").lower()
BASE_URL = os.getenv("BASE_URL", "https://mvxymediator.vercel.app").rstrip("/")

# MongoDB Connection Setup
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]
links_col = db["quick_links"]

# Ensure unique index on "code"
links_col.create_index([("code", ASCENDING)], unique=True)


def generate_secure_code(length=8):
    """Generates a cryptographically secure random alphanumeric code."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_destination_url(url_str):
    """Validates that the URL uses HTTP/HTTPS and strictly matches ALLOWED_DOMAIN."""
    if not url_str:
        return False
    try:
        parsed = urlparse(url_str)
        # Scheme restriction (prevents javascript:, data:, file:, etc.)
        if parsed.scheme not in ("http", "https"):
            return False
        
        # Domain validation
        hostname = parsed.hostname
        if not hostname:
            return False
        
        hostname = hostname.lower()
        # Allows exact domain match or subdomains of ALLOWED_DOMAIN
        if hostname == ALLOWED_DOMAIN or hostname.endswith("." + ALLOWED_DOMAIN):
            return True
        return False
    except Exception:
        return False


# --- Routes ---

@app.route("/api/quick-link", methods=["POST"])
def create_quick_link():
    # 1. API Key Check
    incoming_api_key = request.headers.get("x-api-key")
    if not incoming_api_key or incoming_api_key != API_KEY:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # 2. Parse & Validate Payload
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url")

    if not validate_destination_url(raw_url):
        return jsonify({
            "success": False,
            "error": "Invalid destination URL or domain not allowed."
        }), 400

    # 3. Generate Cryptographic Code & Save to MongoDB
    code = None
    for _ in range(5):  # Retry loop in case of extremely rare collision
        candidate_code = generate_secure_code(8)
        doc = {
            "code": candidate_code,
            "destination": raw_url,
            "type": "quick_link",
            "clicks": 0,
            "createdAt": datetime.now(timezone.utc)
        }
        try:
            links_col.insert_one(doc)
            code = candidate_code
            break
        except DuplicateKeyError:
            continue

    if not code:
        return jsonify({"success": False, "error": "Could not generate link code"}), 500

    encoded_destination = quote(raw_url, safe="")
    quick_url = f"{BASE_URL}/qs/{code}?s={encoded_destination}"

    return jsonify({
        "success": True,
        "code": code,
        "quick_url": quick_url
    }), 201


@app.route("/qs/<code>", methods=["GET"])
def quick_link_page(code):
    # 1. Fetch record strictly from MongoDB using the code parameter
    link_doc = links_col.find_one({"code": code, "type": "quick_link"})
    
    if not link_doc:
        return "Link not found or expired.", 404

    destination_url = link_doc["destination"]

    # Handle button click redirect after countdown
    if request.args.get("action") == "redirect":
        links_col.update_one({"_id": link_doc["_id"]}, {"$inc": {"clicks": 1}})
        return redirect(destination_url)

    # 2. Render HTML countdown page
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MVXY Mediator</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }
            .card {
                background-color: #1e293b;
                padding: 2.5rem;
                border-radius: 12px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
                text-align: center;
                max-width: 400px;
                width: 90%;
            }
            h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #38bdf8; }
            p { color: #94a3b8; font-size: 1rem; }
            .timer {
                font-size: 3rem;
                font-weight: bold;
                margin: 1.5rem 0;
                color: #f43f5e;
            }
            .btn {
                background-color: #38bdf8;
                color: #0f172a;
                border: none;
                padding: 0.75rem 1.75rem;
                font-size: 1rem;
                font-weight: bold;
                border-radius: 6px;
                cursor: pointer;
                transition: opacity 0.2s;
                text-decoration: none;
                display: inline-block;
            }
            .btn:disabled {
                background-color: #475569;
                color: #94a3b8;
                cursor: not-allowed;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>MVXY Mediator</h1>
            <p>Please wait...</p>
            <div class="timer" id="countdown">10</div>
            <a id="continueBtn" href="/qs/{{ code }}?action=redirect" class="btn" style="pointer-events: none; opacity: 0.5;">Wait...</a>
        </div>

        <script>
            let seconds = 10;
            const timerEl = document.getElementById('countdown');
            const btnEl = document.getElementById('continueBtn');

            const interval = setInterval(() => {
                seconds--;
                timerEl.textContent = seconds;
                if (seconds <= 0) {
                    clearInterval(interval);
                    btnEl.textContent = "Continue";
                    btnEl.style.pointerEvents = "auto";
                    btnEl.style.opacity = "1";
                }
            }, 1000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template, code=code)

# For Vercel execution
app = app
