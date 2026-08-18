import os
import json
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from pymongo import MongoClient

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGODB_URI"))
    return _client[os.environ.get("MONGODB_DATABASE", "mvxymediator")]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse code from query (rewritten from /:code)
        query = parse_qs(urlparse(self.path).query)
        code = query.get("code", [None])[0]

        if not code:
            self.send_error(400, "Missing code")
            return

        db = get_db()
        collection = db["links"]
        doc = collection.find_one({"code": code})

        if not doc:
            self.send_error(404, "Short link not found")
            return

        # Increment click count (link used)
        collection.update_one({"code": code}, {"$inc": {"clicks": 1}})

        destination = doc["destination"]
        # Safely embed destination in JavaScript
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
