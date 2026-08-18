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

# Initialize FastAPI App
app = FastAPI(title="MVXY Mediator")

# Retrieve Environment Variables
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "mvxymediator")
API_KEY = os.getenv("API_KEY", "mvxyyy")

# MongoDB Client Setup (Reused across serverless warm invocations)
mongo_client = None

def get_db():
    global mongo_client
    if not mongo_client:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI environment variable is missing.")
        mongo_client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
    return mongo_client[MONGODB_DATABASE]


def generate_unique_code(db, length=10):
    """Generates a cryptographically secure random alphanumeric code."""
    alphabet = string.ascii_lowercase + string.digits
    collection = db["short_links"]
    
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Ensure code is unique in MongoDB
        if not collection.find_one({"code": code}):
            return code


def is_valid_url(url: str) -> bool:
    """Validates destination URL (allows http/https, blocks dangerous schemes)."""
    if not url:
        return False
    
    # Strictly block dangerous schemes
    lowered_url = url.strip().lower()
    banned_schemes = ("javascript:", "data:", "file:", "vbscript:")
    if any(lowered_url.startswith(scheme) for scheme in banned_schemes):
        return False
        
    # Ensure scheme is either http or https
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


@app.get("/api/st")
async def api_shorten(
    request: Request,
    api: str = Query(None),
    url: str = Query(None)
):
    """
    1. Validates API Key.
    2. Validates destination URL.
    3. Generates unique random code and saves to MongoDB.
    4. HTTP 302 redirects to https://<host>/<code>
    """
    # 1. API Key Check
    if api != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )

    # 2. Destination URL Validation
    if not url or not is_valid_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination URL. Must begin with http:// or https://"
        )

    db = get_db()
    collection = db["short_links"]

    # 3. Generate Random Code & Store Record
    code = generate_unique_code(db)
    document = {
        "code": code,
        "destination": url,
        "clicks": 0,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    collection.insert_one(document)

    # 4. Construct Short URL dynamically from Request Hostname
    # Uses x-forwarded-proto or request scheme to determine SSL status
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    redirect_destination = f"{scheme}://{host}/{code}"

    # Return HTTP 302 Redirect
    return RedirectResponse(url=redirect_destination, status_code=status.HTTP_302_FOUND)


@app.get("/{code}", response_class=HTMLResponse)
async def mediator_page(code: str):
    """
    Renders the countdown page for the generated short-link code.
    """
    # Ignore favicon requests
    if code == "favicon.ico":
        raise HTTPException(status_code=404, detail="Not Found")

    db = get_db()
    collection = db["short_links"]
    
    # Retrieve code record from MongoDB
    record = collection.find_one({"code": code})
    if not record:
        raise HTTPException(status_code=404, detail="Link not found or expired")

    destination_url = record["destination"]

    # Render HTML Page with Countdown and Continue Button
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MVXY Mediator</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #0f172a;
                color: #f8fafc;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }}
            .card {{
                background: #1e293b;
                border: 1px solid #334155;
                padding: 2.5rem;
                border-radius: 12px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
                text-align: center;
                max-width: 420px;
                width: 90%;
            }}
            h1 {{
                font-size: 1.5rem;
                margin-bottom: 0.5rem;
                color: #38bdf8;
            }}
            .subtitle {{
                font-size: 1rem;
                color: #94a3b8;
                margin-bottom: 1.5rem;
            }}
            .timer {{
                font-size: 3rem;
                font-weight: bold;
                color: #f59e0b;
                margin: 1rem 0;
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
                text-decoration: none;
                display: inline-block;
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
        </style>
    </head>
    <body>
        <div class="card">
            <h1>MVXY MEDIATOR</h1>
            <div class="subtitle">Please wait...</div>
            <div class="timer" id="countdown">10</div>
            <button id="continueBtn" class="btn" disabled>Continue</button>
        </div>

        <script>
            let timeLeft = 10;
            const countdownEl = document.getElementById('countdown');
            const continueBtn = document.getElementById('continueBtn');
            const destination = "{destination_url}";

            const timer = setInterval(() => {{
                timeLeft--;
                if (timeLeft >= 0) {{
                    countdownEl.textContent = timeLeft;
                }}
                
                if (timeLeft <= 0) {{
                    clearInterval(timer);
                    continueBtn.disabled = false;
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
