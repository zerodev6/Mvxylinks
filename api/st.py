import os
import re
import secrets
import string
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
from pymongo import MongoClient
from datetime import datetime, timezone

# Environment Variables
MONGODB_URI = "mongodb+srv://maheesharashmi22_db_user:UVjtznEJD5UF3e8x@cluster0.l7gxl3n.mongodb.net"
MONGODB_DATABASE = "mvxymediator"
API_KEY = "mvxyyy"

# Initialize MongoDB Client lazily for Serverless execution
client = None
def get_db():
    global client
    if client is None:
        client = MongoClient(MONGODB_URI)
    return client[MONGODB_DATABASE]

def generate_code(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)
    except Exception:
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        # 1. API Key Authentication
        query_api_key = params.get('api', [None])[0]
        header_api_key = self.headers.get('x-api-key')
        provided_key = query_api_key or header_api_key

        if provided_key != API_KEY:
            self._send_response(401, {"success": False, "error": "Unauthorized: Invalid or missing API key"})
            return

        # 2. Extract & Validate URL
        target_url = params.get('url', [None])[0]
        if not target_url or not is_valid_url(target_url):
            self._send_response(400, {"success": False, "error": "Bad Request: Invalid or missing target URL"})
            return

        # 3. Connect DB & Store Link
        try:
            db = get_db()
            links_collection = db['links']
            
            # Ensure index on code for quick lookup
            links_collection.create_index("code", unique=True)

            # Generate unique random code
            code = generate_code()
            while links_collection.find_one({"code": code}):
                code = generate_code()

            record = {
                "code": code,
                "destination": target_url,
                "clicks": 0,
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            links_collection.insert_one(record)

            # 4. Determine Dynamic Hostname
            host = self.headers.get('host', 'mvxymediator.vercel.app')
            scheme = 'https' if 'localhost' not in host else 'http'
            short_url = f"{scheme}://{host}/{code}"

            self._send_response(200, {
                "success": True,
                "url": short_url,
                "code": code
            })

        except Exception as e:
            self._send_response(500, {"success": False, "error": str(e)})

    def _send_response(self, status_code, body):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode('utf-8'))
