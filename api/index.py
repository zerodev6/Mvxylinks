import os
import json
from urllib.parse import urlparse, quote, unquote
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from pymongo import MongoClient
from pymongo.errors import PyMongoError

app = Flask(__name__)

# --------------------------
# Environment & DB setup
# --------------------------
MONGODB_URI = "mongodb+srv://maheesharashmi22_db_user:UVjtznEJD5UF3e8x@cluster0.l7gxl3n.mongodb.net"
MONGODB_DATABASE = "mvxymediator"
API_KEY = "mvxyyh"

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI environment variable is required")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable is required")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DATABASE]
quick_links = db.quick_links

# --------------------------
# URL validation
# --------------------------
def is_valid_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False

def validate_and_decode_url(s):
    if not s:
        return None, "Missing URL parameter"
    try:
        decoded = unquote(s)
    except Exception:
        return None, "Invalid URL encoding"
    if not is_valid_url(decoded):
        return None, "Invalid URL. Only http:// and https:// are allowed."
    return decoded, None

# --------------------------
# API: Create Quick Link
# --------------------------
@app.route('/api/create', methods=['POST'])
def create_quick_link():
    # API Key authentication
    api_key = request.headers.get('x-api-key')
    if not api_key or api_key != API_KEY:
        return jsonify({"error": "Invalid or missing API key"}), 401

    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    destination = data['url']
    if not is_valid_url(destination):
        return jsonify({"error": "Invalid URL. Only http:// and https:// are allowed."}), 400

    # Upsert into MongoDB (create if not exists, but don't increment clicks yet)
    try:
        quick_links.update_one(
            {"destination": destination},
            {"$setOnInsert": {"type": "quick_link", "createdAt": datetime.utcnow()}},
            upsert=True
        )
    except PyMongoError as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Build quick URL using the current host
    base_url = request.host_url.rstrip('/')
    encoded_dest = quote(destination, safe='')
    quick_url = f"{base_url}/qs/mvxyyy?s={encoded_dest}"

    return jsonify({
        "success": True,
        "quick_url": quick_url
    }), 201

# --------------------------
# Quick Link Page (countdown)
# --------------------------
@app.route('/qs/mvxyyy')
def quick_link_page():
    s = request.args.get('s')
    if not s:
        return "Missing 's' parameter", 400

    destination, error = validate_and_decode_url(s)
    if error:
        return f"Error: {error}", 400

    # Increment clicks (upsert if missing – e.g., manual access)
    try:
        quick_links.update_one(
            {"destination": destination},
            {"$inc": {"clicks": 1}, "$setOnInsert": {"type": "quick_link", "createdAt": datetime.utcnow()}},
            upsert=True
        )
    except PyMongoError as e:
        # Log but still serve the page
        app.logger.error(f"Failed to update clicks: {e}")

    # Render countdown page with safe injection of destination
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>MVXY Mediator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f7fa;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 16px;
        }
        .container {
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.1);
            padding: 32px 24px;
            max-width: 420px;
            width: 100%;
            text-align: center;
        }
        .logo {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 8px;
        }
        .logo span {
            color: #e94560;
        }
        .subtitle {
            color: #666;
            font-size: 14px;
            margin-bottom: 24px;
        }
        .countdown-circle {
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 24px auto;
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: #e94560;
            color: white;
            font-size: 48px;
            font-weight: bold;
            transition: background 0.3s;
        }
        .status {
            font-size: 18px;
            color: #333;
            margin-bottom: 24px;
        }
        .btn {
            display: inline-block;
            width: 100%;
            padding: 14px 0;
            font-size: 18px;
            font-weight: 600;
            border: none;
            border-radius: 50px;
            background: #e94560;
            color: white;
            cursor: pointer;
            transition: opacity 0.3s, background 0.3s;
            text-decoration: none;
        }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .btn:not(:disabled):hover {
            background: #c73652;
        }
        .footer {
            margin-top: 24px;
            font-size: 12px;
            color: #aaa;
        }
        .footer a {
            color: #e94560;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">MVXY<span>Mediator</span></div>
        <div class="subtitle">Redirecting you securely</div>
        <div id="countdown" class="countdown-circle">10</div>
        <div class="status" id="status">Please wait...</div>
        <button id="continueBtn" class="btn" disabled>Continue</button>
        <div class="footer">Powered by MVXY</div>
    </div>

    <script>
        (function() {
            var countdown = 10;
            var timerElement = document.getElementById('countdown');
            var statusElement = document.getElementById('status');
            var continueBtn = document.getElementById('continueBtn');
            var destination = {{ dest|tojson }};

            function updateDisplay() {
                timerElement.textContent = countdown;
                if (countdown > 0) {
                    statusElement.textContent = 'Please wait...';
                    continueBtn.disabled = true;
                    continueBtn.textContent = 'Continue';
                } else {
                    statusElement.textContent = 'Ready to proceed';
                    continueBtn.disabled = false;
                    continueBtn.textContent = 'Continue →';
                }
            }

            function countdownTick() {
                if (countdown > 0) {
                    countdown--;
                    updateDisplay();
                    setTimeout(countdownTick, 1000);
                }
            }

            continueBtn.addEventListener('click', function() {
                if (!continueBtn.disabled) {
                    window.location.href = destination;
                }
            });

            // Start countdown
            updateDisplay();
            setTimeout(countdownTick, 1000);
        })();
    </script>
</body>
</html>
    """
    return render_template_string(html_template, dest=destination), 200

# --------------------------
# Local development
# --------------------------
if __name__ == '__main__':
    app.run(debug=True)
