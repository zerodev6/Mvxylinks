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
API_KEY = "mvxyyy"

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

# Handles both /api/st and /st paths for Vercel compatibility
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
  <title>mvxy.site | Download Links</title>
  <style>
    :root {{
      --bg-light: #f8fafc;
      --card-bg: #ffffff;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --accent-blue: #2563eb;
      --btn-green: #10b981;
      --btn-green-hover: #059669;
      --icon-pink: #f43f5e;
      --icon-teal: #14b8a6;
      --border-color: #e2e8f0;
      --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}

    body {{
      background-color: var(--bg-light);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      position: relative;
      overflow-x: hidden;
    }}

    /* Abstract Soft Curves at Bottom */
    body::after {{
      content: '';
      position: fixed;
      bottom: -150px;
      left: 50%;
      transform: translateX(-50%);
      width: 600px;
      height: 300px;
      background: radial-gradient(circle, rgba(147, 197, 253, 0.3) 0%, rgba(196, 181, 253, 0.25) 50%, rgba(255, 255, 255, 0) 70%);
      border-radius: 50%;
      z-index: -1;
      pointer-events: none;
    }}

    /* Main Card Container */
    .app-card {{
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 24px;
      padding: 2.25rem 1.75rem;
      width: 100%;
      max-width: 440px;
      text-align: center;
      box-shadow: var(--shadow);
      position: relative;
    }}

    /* Header */
    .top-bar {{
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
      font-weight: 500;
    }}

    .main-heading {{
      font-size: 1.3rem;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 1.25rem;
    }}

    /* Circular SVG Timer */
    .timer-container {{
      position: relative;
      width: 130px;
      height: 130px;
      margin: 0 auto 1.25rem auto;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .timer-svg {{
      transform: rotate(-90deg);
      width: 100%;
      height: 100%;
    }}

    .circle-bg {{
      fill: none;
      stroke: #0f172a;
      stroke-width: 3;
    }}

    .circle-progress {{
      fill: none;
      stroke: var(--accent-blue);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-dasharray: 377;
      stroke-dashoffset: 0;
      transition: stroke-dashoffset 1s linear, stroke 0.3s ease;
    }}

    .countdown-number {{
      position: absolute;
      font-size: 2.75rem;
      font-weight: 700;
      color: var(--text-main);
      font-variant-numeric: tabular-nums;
    }}

    /* Green Status / Action Button */
    .action-btn {{
      background: var(--btn-green);
      color: #ffffff;
      font-weight: 700;
      font-size: 0.95rem;
      letter-spacing: 0.05em;
      padding: 0.85rem 1.5rem;
      border-radius: 99px;
      border: none;
      width: 100%;
      max-width: 280px;
      margin: 0 auto 1.5rem auto;
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
      cursor: wait;
      display: block;
      text-decoration: none;
      transition: all 0.3s ease;
    }}

    .action-btn.ready {{
      cursor: pointer;
      background: var(--accent-blue);
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
      animation: pulseBtn 2s infinite;
    }}

    .action-btn.ready:hover {{
      background: #1d4ed8;
      transform: translateY(-1px);
    }}

    /* Section Boxes below Timer */
    .info-list {{
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
      border-top: 1px solid var(--border-color);
      padding-top: 1.25rem;
      margin-top: 0.5rem;
    }}

    .info-item {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.35rem;
    }}

    .icon-circle {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 0.15rem;
    }}

    .icon-circle.blue {{
      background: #eff6ff;
      color: var(--accent-blue);
    }}

    .icon-circle.pink {{
      background: #ffe4e6;
      color: var(--icon-pink);
    }}

    .icon-circle.teal {{
      background: #ccfbf1;
      color: var(--icon-teal);
    }}

    .item-title {{
      font-size: 1rem;
      font-weight: 700;
      color: var(--text-main);
    }}

    .item-desc {{
      font-size: 0.85rem;
      color: var(--text-muted);
      line-height: 1.4;
    }}

    .telegram-link {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      margin-top: 0.4rem;
      color: #0088cc;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.875rem;
    }}

    .telegram-link:hover {{
      text-decoration: underline;
    }}

    .copyright {{
      margin-top: 1.75rem;
      font-size: 0.775rem;
      color: var(--text-muted);
      text-align: center;
    }}

    @keyframes pulseBtn {{
      0% {{ box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }}
      70% {{ box-shadow: 0 0 0 10px rgba(37, 99, 235, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }}
    }}
  </style>
</head>
<body>

  <div class="app-card">
    
    <div class="top-bar">Mediator Page | Please Wait.</div>
    <h1 class="main-heading" id="mainHeading">Links Page is Almost Ready 🚀</h1>

    <!-- CIRCULAR TIMER -->
    <div class="timer-container">
      <svg class="timer-svg" viewBox="0 0 130 130">
        <circle class="circle-bg" cx="65" cy="65" r="60"></circle>
        <circle class="circle-progress" id="progressRing" cx="65" cy="65" r="60"></circle>
      </svg>
      <div class="countdown-number" id="timerNumber">12</div>
    </div>

    <!-- ACTION BUTTON -->
    <a href="#" class="action-btn" id="actionBtn" onclick="handleBtnClick(event)">PLEASE WAIT...</a>

    <!-- EVERYTHING UNDER THE TIMER -->
    <div class="info-list">
      
      <!-- 1. Download Servers -->
      <div class="info-item">
        <div class="icon-circle blue">
          <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
        <div class="item-title">Download Servers</div>
        <div class="item-desc">mvxy.site Provide Fastest Download</div>
      </div>

      <!-- 2. Multiple Links -->
      <div class="info-item">
        <div class="icon-circle pink">
          <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v2.25A2.25 2.25 0 0113.5 21.75h-9a2.25 2.25 0 01-2.25-2.25v-9A2.25 2.25 0 014.5 8.25H6.75m3 0h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9A2.25 2.25 0 019.75 8.25z" />
          </svg>
        </div>
        <div class="item-title">Multiple Links</div>
        <div class="item-desc">Fastest &amp; Reliable Links are Available for Downloading.</div>
      </div>

      <!-- 3. Telegram Request & Contact -->
      <div class="info-item">
        <div class="icon-circle teal">
          <svg width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
          </svg>
        </div>
        <div class="item-title">Request</div>
        <div class="item-desc">Users can request us for Updating Links by Contacting Via Telegram.</div>
        <a href="https://t.me" target="_blank" class="telegram-link">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.562 8.161c-.18.717-.962 4.084-1.362 5.411-.168.56-.505.748-.83.766-.709.039-1.247-.461-1.932-.91-.107-.07-.213-.142-.321-.213-1.073-.705-1.716-1.127-2.76-1.815-.316-.208-.553-.33-.509-.646.037-.267.382-.533.722-.843 1.488-1.353 2.822-2.58 2.883-2.656.082-.102.138-.224.03-.284-.108-.06-.264-.025-.378 0-.161.035-2.715 1.724-3.832 2.481-.358.242-.682.362-.973.355-.322-.007-.942-.182-1.403-.332-.566-.184-1.017-.282-.977-.595.021-.163.245-.33.672-.5 2.633-1.147 4.39-1.905 5.271-2.274 2.512-1.048 3.033-1.23 3.374-1.236.075-.001.242.018.351.106.092.075.117.176.128.247.012.078.026.252.014.394z"/>
          </svg>
          Contact via Telegram
        </a>
      </div>

    </div>

  </div>

  <div class="copyright">
    &copy; 2024 mvxy.site, All Rights Reserved
  </div>

  <script>
    const TARGET_URL = "{destination_url}";
    const DURATION = 12;
    let secondsLeft = DURATION;

    const CIRCUMFERENCE = 2 * Math.PI * 60;
    const timerNumberEl = document.getElementById('timerNumber');
    const progressRingEl = document.getElementById('progressRing');
    const actionBtn = document.getElementById('actionBtn');
    const mainHeading = document.getElementById('mainHeading');

    progressRingEl.style.strokeDasharray = CIRCUMFERENCE;

    const timer = setInterval(() => {{
      secondsLeft--;
      if (secondsLeft >= 0) {{
        timerNumberEl.textContent = secondsLeft;
        const offset = CIRCUMFERENCE - (secondsLeft / DURATION) * CIRCUMFERENCE;
        progressRingEl.style.strokeDashoffset = offset;
      }}

      if (secondsLeft <= 0) {{
        clearInterval(timer);
        onCountdownComplete();
      }}
    }}, 1000);

    function onCountdownComplete() {{
      timerNumberEl.innerHTML = `
        <svg width="40" height="40" fill="none" stroke="var(--btn-green)" stroke-width="3" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      `;
      mainHeading.textContent = "Your Links are Ready! 🎉";
      actionBtn.textContent = "GET LINKS NOW";
      actionBtn.classList.add('ready');
      actionBtn.href = TARGET_URL;
    }}

    function handleBtnClick(e) {{
      if (secondsLeft > 0) {{
        e.preventDefault();
      }}
    }}
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content, status_code=200)
