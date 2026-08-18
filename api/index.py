import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pymongo import MongoClient
import html

MONGODB_URI = "mongodb+srv://maheesharashmi22_db_user:UVjtznEJD5UF3e8x@cluster0.l7gxl3n.mongodb.net"
MONGODB_DATABASE = "mvxymediator"

client = None
def get_db():
    global client
    if client is None:
        client = MongoClient(MONGODB_URI)
    return client[MONGODB_DATABASE]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        code = params.get('code', [None])[0]
        action = params.get('action', [None])[0]

        if not code:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>404 Not Found</h1>")
            return

        db = get_db()
        links_collection = db['links']

        # Action handling for redirect trigger (Increments Click Counter)
        if action == "redirect":
            doc = links_collection.find_one_and_update(
                {"code": code},
                {"$inc": {"clicks": 1}}
            )
            if doc and "destination" in doc:
                self.send_response(302)
                self.send_header("Location", doc["destination"])
                self.end_headers()
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Link not found or expired.")
                return

        # Render Mediator Countdown Page
        link_doc = links_collection.find_one({"code": code})
        if not link_doc:
            self.send_response(404)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Link Not Found</h1>")
            return

        redirect_endpoint = f"/{code}?action=redirect"
        safe_endpoint = html.escape(redirect_endpoint)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MVXY Mediator</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 40px 30px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            font-size: 1.5rem;
            color: #38bdf8;
            margin-bottom: 24px;
            letter-spacing: 1px;
        }}
        .status {{
            font-size: 1rem;
            color: #94a3b8;
            margin-bottom: 16px;
        }}
        .timer {{
            font-size: 3.5rem;
            font-weight: 700;
            color: #f43f5e;
            margin: 20px 0;
            font-variant-numeric: tabular-nums;
        }}
        .btn {{
            width: 100%;
            padding: 14px;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            background: #38bdf8;
            color: #0f172a;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .btn:disabled {{
            background: #475569;
            color: #94a3b8;
            cursor: not-allowed;
            opacity: 0.6;
        }}
        .btn:not(:disabled):hover {{
            background: #7dd3fc;
            transform: translateY(-1px);
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>MVXY MEDIATOR</h1>
        <div class="status" id="status-text">Please wait...</div>
        <div class="timer" id="countdown">10</div>
        <button class="btn" id="continue-btn" disabled onclick="window.location.href='{safe_endpoint}'">
            Continue
        </button>
    </div>

    <script>
        let seconds = 10;
        const countdownEl = document.getElementById('countdown');
        const statusEl = document.getElementById('status-text');
        const btn = document.getElementById('continue-btn');

        const timer = setInterval(() => {{
            seconds--;
            if (seconds >= 0) {{
                countdownEl.textContent = seconds;
            }}
            if (seconds <= 0) {{
                clearInterval(timer);
                statusEl.textContent = "Your link is ready!";
                countdownEl.style.color = "#4ade80";
                btn.disabled = false;
            }}
        }}, 1000);
    </script>
</body>
</html>
"""

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
