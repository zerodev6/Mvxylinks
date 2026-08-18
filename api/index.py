import os
import re
import secrets
import string
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Query, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from pymongo import MongoClient
from pymongo.server_api import ServerApi

app = FastAPI(title="MVXY Mediator")

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "mvxymediator")
API_KEY = os.getenv("API_KEY", "mvxyyy")

mongo_client = None

def get_db():
    global mongo_client
    if not mongo_client:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI environment variable is missing.")
        mongo_client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
    return mongo_client[MONGODB_DATABASE]

def generate_unique_code(db, length=10):
    alphabet = string.ascii_lowercase + string.digits
    collection = db["short_links"]
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not collection.find_one({"code": code}):
            return code

def is_valid_url(url: str) -> bool:
    if not url:
        return False
    lowered_url = url.strip().lower()
    banned_schemes = ("javascript:", "data:", "file:", "vbscript:")
    if any(lowered_url.startswith(scheme) for scheme in banned_schemes):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

# Note: Handles both /api/st and /st paths to ensure Vercel compatibility
@app.get("/api/st")
@app.get("/st")
async def api_shorten(
    request: Request,
    api: str = Query(None),
    url: str = Query(None)
):
    if api != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    if not url or not is_valid_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination URL. Must begin with http:// or https://"
        )

    db = get_db()
    collection = db["short_links"]

    code = generate_unique_code(db)
    document = {
        "code": code,
        "destination": url,
        "clicks": 0,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    collection.insert_one(document)

    scheme = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("host", request.url.netloc)
    redirect_destination = f"{scheme}://{host}/{code}"

    return RedirectResponse(url=redirect_destination, status_code=status.HTTP_302_FOUND)


@app.get("/{code}", response_class=HTMLResponse)
async def mediator_page(code: str):
    if code in ("favicon.ico", "api", "st"):
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    collection = db["short_links"]
    
    record = collection.find_one({"code": code})
    if not record:
        raise HTTPException(status_code=404, detail="Link not found or expired")

    destination_url = record["destination"]

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mediator Page | Please Wait.</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }}
            .card {{
                background: #1e293b;
                border: 1px solid #334155;
                padding: 2rem;
                border-radius: 12px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
                max-width: 500px;
                width: 100%;
                text-align: center;
            }}
            .header {{
                font-size: 0.9rem;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 0.5rem;
            }}
            .main-title {{
                font-size: 1.8rem;
                font-weight: bold;
                color: #38bdf8;
                margin-bottom: 0.2rem;
            }}
            .subtitle {{
                color: #94a3b8;
                margin-bottom: 1.5rem;
            }}
            .countdown {{
                font-size: 4rem;
                font-weight: bold;
                color: #f59e0b;
                margin: 0.5rem 0;
            }}
            .wait-text {{
                font-size: 1rem;
                color: #94a3b8;
                margin-bottom: 1rem;
            }}
            .download-servers {{
                font-size: 1.2rem;
                font-weight: bold;
                color: #f8fafc;
                margin-top: 1rem;
            }}
            .fastest-text {{
                font-size: 0.9rem;
                color: #94a3b8;
                margin-bottom: 1.5rem;
            }}
            .btn {{
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                padding: 0.8rem 2rem;
                font-size: 1rem;
                font-weight: 600;
                border-radius: 6px;
                cursor: pointer;
                transition: background-color 0.2s, opacity 0.2s;
                width: 100%;
            }}
            .btn:disabled {{
                background-color: #475569;
                color: #94a3b8;
                cursor: not-allowed;
                opacity: 0.6;
            }}
            .btn:hover:not(:disabled) {{
                background-color: #2563eb;
            }}
            .footer {{
                margin-top: 2rem;
                border-top: 1px solid #334155;
                padding-top: 1.5rem;
            }}
            .footer-heading {{
                font-size: 1.1rem;
                font-weight: bold;
                color: #f8fafc;
            }}
            .footer-text {{
                font-size: 0.9rem;
                color: #94a3b8;
                margin: 0.3rem 0;
            }}
            .footer-request {{
                font-weight: bold;
                color: #f8fafc;
                margin-top: 1rem;
            }}
            .footer-request-text {{
                font-size: 0.9rem;
                color: #94a3b8;
            }}
            .copyright {{
                font-size: 0.8rem;
                color: #64748b;
                margin-top: 1rem;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">Mediator Page | Please Wait.</div>
            <div class="main-title">Links Page is Almost Ready 🚀</div>
            <div class="countdown" id="countdown">10</div>
            <div class="wait-text">PLEASE WAIT...</div>
            <div class="download-servers">Download Servers</div>
            <div class="fastest-text">HDHub4u Provide Fastest Download</div>
            <button id="continueBtn" class="btn" disabled>Get Link</button>
            <div class="footer">
                <div class="footer-heading">Multiple Links</div>
                <div class="footer-text">Fastest & Reliable Links are Available for Downloading.</div>
                <div class="footer-request">Request</div>
                <div class="footer-request-text">Users can request us for Updating Links by Contacting Via Telegram</div>
                <div class="copyright">© 2024 mvxy.site, All Rights Reserved</div>
            </div>
        </div>
        <script>
            let timeLeft = 10;
            const countdownEl = document.getElementById('countdown');
            const continueBtn = document.getElementById('continueBtn');
            const destination = "{destination_url}";

            const timer = setInterval(() => {{
                timeLeft--;
                if (timeLeft >= 0) countdownEl.textContent = timeLeft;
                if (timeLeft <= 0) {{
                    clearInterval(timer);
                    continueBtn.disabled = false;
                    continueBtn.textContent = "Get Link";
                }}
            }}, 1000);

            continueBtn.addEventListener('click', () => {{
                window.location.href = destination;
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)
