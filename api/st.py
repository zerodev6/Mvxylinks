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
        # Parse query parameters
        query = parse_qs(urlparse(self.path).query)
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

        # Check if the client is a browser (Accept header contains text/html)
        accept_header = self.headers.get("Accept", "")
        is_browser = "text/html" in accept_header

        # Redirect if requested by browser or explicit redirect param
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

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
