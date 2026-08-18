import os
import json
import secrets
import string
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from pymongo import MongoClient

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGODB_URI"))
    return _client[os.environ.get("MONGODB_DATABASE", "mvxymediator")]

def generate_code(length=10):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return False
        if not parsed.netloc:
            return False
        if parsed.scheme.lower() in ("javascript", "data", "file", "vbscript"):
            return False
        return True
    except Exception:
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)

        # --- Shorten API endpoint ---
        if path == "/api/st":
            self.handle_shorten(query)
            return

        # --- Root (landing page) ---
        if path == "/":
            self.show_landing_page()
            return

        # --- Short link (single segment code) ---
        # Strip leading slash
        code = path.lstrip("/")
        if "/" in code:
            self.send_error(404, "Not found")
            return

        self.handle_short_link(code)

    def handle_shorten(self, query):
        api_key = query.get("api", [None])[0] or self.headers.get("x-api-key")
        url = query.get("url", [None])[0]
        redirect_flag = query.get("redirect", ["false"])[0].lower() == "true"

        # Verify API key
        expected_key = os.environ.get("API_KEY")
        if not expected_key or api_key != expected_key:
            self.send_json(401, {"success": False, "error": "Invalid or missing API key"})
            return

        # Validate URL
        if not url or not is_safe_url(url):
            self.send_json(400, {"success": False, "error": "Invalid or unsafe URL"})
            return

        # Generate unique code
        db = get_db()
        collection = db["links"]
        code = generate_code()
        while collection.find_one({"code": code}):
            code = generate_code()

        # Insert document
        doc = {
            "code": code,
            "destination": url,
            "clicks": 0,
            "createdAt": datetime.utcnow()
        }
        collection.insert_one(doc)

        # Build short link using Vercel hostname
        host = self.headers.get("host", "localhost")
        short_url = f"https://{host}/{code}"

        # If browser or redirect requested, send HTTP redirect
        accept_header = self.headers.get("Accept", "")
        is_browser = "text/html" in accept_header

        if is_browser or redirect_flag:
            self.send_response(302)
            self.send_header("Location", short_url)
            self.end_headers()
        else:
            self.send_json(200, {
                "success": True,
                "url": short_url,
                "code": code
            })

    def handle_short_link(self, code):
        db = get_db()
        collection = db["links"]
        doc = collection.find_one({"code": code})

        if not doc:
            self.send_error(404, "Short link not found")
            return

        # Increment click count
        collection.update_one({"code": code}, {"$inc": {"clicks": 1}})

        destination = doc["destination"]
        destination_json = json.dumps(destination)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MVXY Mediator</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 2rem;
            text-align: center;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #302b63;
            font-size: 2rem;
            letter-spacing: 2px;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        p {{
            color: #555;
            margin-bottom: 1.5rem;
            font-size: 1.1rem;
        }}
        #countdown {{
            font-size: 4rem;
            font-weight: bold;
            color: #302b63;
            margin-bottom: 1.5rem;
            transition: transform 0.2s;
        }}
        button {{
            background: #302b63;
            color: white;
            border: none;
            border-radius: 30px;
            padding: 12px 30px;
            font-size: 1.2rem;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            transition: background 0.3s, opacity 0.3s;
            letter-spacing: 1px;
        }}
        button:disabled {{
            background: #ccc;
            cursor: not-allowed;
            opacity: 0.6;
        }}
        button:not(:disabled):hover {{
            background: #1f1a4a;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>MVXY MEDIATOR</h1>
        <p>Please wait...</p>
        <div id="countdown">10</div>
        <button id="continueBtn" disabled>Continue</button>
    </div>
    <script>
        const destination = {destination_json};
        let count = 10;
        const countdownEl = document.getElementById('countdown');
        const continueBtn = document.getElementById('continueBtn');

        const interval = setInterval(() => {{
            count--;
            countdownEl.textContent = count;
            if (count <= 0) {{
                clearInterval(interval);
                countdownEl.textContent = '0';
                continueBtn.disabled = false;
                continueBtn.textContent = 'Continue';
            }}
        }}, 1000);

        continueBtn.addEventListener('click', () => {{
            window.location.href = destination;
        }});
    </script>
</body>
</html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def show_landing_page(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MVXY Mediator</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .card {
            background: white;
            padding: 2rem;
            border-radius: 20px;
            text-align: center;
            max-width: 400px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }
        h1 {
            color: #302b63;
            margin-bottom: 1rem;
        }
        p {
            color: #555;
        }
        a {
            color: #302b63;
            font-weight: bold;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>MVXY Mediator</h1>
        <p>This is a URL shortener with a countdown mediator.</p>
        <p>Use the API at <code>/api/st</code> to create short links.</p>
    </div>
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
