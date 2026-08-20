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
        # Synchronous client connection cached safely for Vercel serverless environment
        mongo_client = MongoClient(
            MONGODB_URI, 
            server_api=ServerApi('1'),
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )
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
  <title>mvxy.site | Secure Link Hub</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #080808;
      --card-bg: #111111;
      --border-color: #222222;
      --text-main: #ffffff;
      --text-muted: #888888;
      --primary: #E50914;
      --btn-green: #10b981;
      --accent-blue: #229ED9;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Outfit', sans-serif;
    }}

    body {{
      background-color: var(--bg);
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

    body::after {{
      content: '';
      position: fixed;
      bottom: -200px;
      left: 50%;
      transform: translateX(-50%);
      width: 500px;
      height: 250px;
      background: radial-gradient(circle, rgba(229,9,20,0.15) 0%, rgba(0,0,0,0) 70%);
      border-radius: 50%;
      z-index: -1;
      pointer-events: none;
    }}

    .app-card {{
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 24px;
      padding: 2.5rem 1.75rem;
      width: 100%;
      max-width: 440px;
      text-align: center;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      position: relative;
    }}

    .top-bar {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}

    .main-heading {{
      font-size: 1.4rem;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 1.5rem;
    }}

    .timer-container {{
      position: relative;
      width: 130px;
      height: 130px;
      margin: 0 auto 1.5rem auto;
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
      stroke: #222222;
      stroke-width: 4;
    }}

    .circle-progress {{
      fill: none;
      stroke: var(--primary);
      stroke-width: 5;
      stroke-linecap: round;
      stroke-dasharray: 377;
      stroke-dashoffset: 0;
      transition: stroke-dashoffset 0.2s linear;
    }}

    .countdown-number {{
      position: absolute;
      font-size: 2.75rem;
      font-weight: 800;
      color: var(--text-main);
      font-variant-numeric: tabular-nums;
    }}

    .action-btn {{
      background: #222222;
      color: var(--text-muted);
      font-weight: 700;
      font-size: 0.95rem;
      letter-spacing: 0.05em;
      padding: 0.9rem 1.5rem;
      border-radius: 99px;
      border: none;
      width: 100%;
      max-width: 280px;
      margin: 0 auto 1.5rem auto;
      cursor: not-allowed;
      display: block;
      text-decoration: none;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}

    .action-btn.ready {{
      cursor: pointer;
      background: var(--primary);
      color: #ffffff;
      box-shadow: 0 4px 20px rgba(229, 9, 20, 0.4);
      animation: pulseBtn 2s infinite;
    }}

    .action-btn.ready:hover {{
      background: #ff1e2a;
      transform: translateY(-2px);
    }}

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
      width: 40px;
      height: 40px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 0.15rem;
    }}

    .icon-circle.red {{
      background: rgba(229,9,20,0.1);
      color: var(--primary);
    }}

    .icon-circle.blue {{
      background: rgba(34,158,217,0.1);
      color: var(--accent-blue);
    }}

    .item-title {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #eee;
    }}

    .item-desc {{
      font-size: 0.8rem;
      color: var(--text-muted);
      line-height: 1.4;
    }}

    .telegram-link {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      margin-top: 0.4rem;
      color: var(--accent-blue);
      text-decoration: none;
      font-weight: 600;
      font-size: 0.85rem;
    }}

    .telegram-link:hover {{
      text-decoration: underline;
    }}

    .copyright {{
      margin-top: 1.5rem;
      font-size: 0.75rem;
      color: var(--text-muted);
      text-align: center;
    }}

    @keyframes pulseBtn {{
      0% {{ box-shadow: 0 0 0 0 rgba(229, 9, 20, 0.4); }}
      70% {{ box-shadow: 0 0 0 12px rgba(229, 9, 20, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(229, 9, 20, 0); }}
    }}
  </style>
</head>
<body>

  <div class="app-card">
    <div class="top-bar">Secure Link Protection</div>
    <h1 class="main-heading" id="mainHeading">Preparing Secure Destination...</h1>

    <div class="timer-container">
      <svg class="timer-svg" viewBox="0 0 130 130">
        <circle class="circle-bg" cx="65" cy="65" r="60"></circle>
        <circle class="circle-progress" id="progressRing" cx="65" cy="65" r="60"></circle>
      </svg>
      <div class="countdown-number" id="timerNumber">12</div>
    </div>

    <a href="#" class="action-btn" id="actionBtn" onclick="handleBtnClick(event)">PLEASE WAIT...</a>

    <div class="info-list">
      <div class="info-item">
        <div class="icon-circle red">
          <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>
          </svg>
        </div>
        <div class="item-title">High Speed Mirrors</div>
        <div class="item-desc">Optimized servers engineered for instant download speeds.</div>
      </div>

      <div class="info-item">
        <div class="icon-circle blue">
          <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0z"/>
          </svg>
        </div>
        <div class="item-title">Community Support</div>
        <div class="item-desc">Join our official network for reporting broken files or requesting content.</div>
        <a href="https://t.me/mvxyoffcail" target="_blank" class="telegram-link">
          <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.562 8.161c-.18.717-.962 4.084-1.362 5.411-.168.56-.505.748-.83.766-.709.039-1.247-.461-1.932-.91-.107-.07-.213-.142-.321-.213-1.073-.705-1.716-1.127-2.76-1.815-.316-.208-.553-.33-.509-.646.037-.267.382-.533.722-.843 1.488-1.353 2.822-2.58 2.883-2.656.082-.102.138-.224.03-.284-.108-.06-.264-.025-.378 0-.161.035-2.715 1.724-3.832 2.481-.358.242-.682.362-.973.355-.322-.007-.942-.182-1.403-.332-.566-.184-1.017-.282-.977-.595.021-.163.245-.33.672-.5 2.633-1.147 4.39-1.905 5.271-2.274 2.512-1.048 3.033-1.23 3.374-1.236.075-.001.242.018.351.106.092.075.117.176.128.247.012.078.026.252.014.394z"/>
          </svg>
          Open Telegram Support
        </a>
      </div>
    </div>
  </div>

  <div class="copyright">
    &copy; 2026 MVXY. All Rights Reserved.
  </div>

  <script>
    const TARGET_URL = "{destination_url}";
    const DURATION = 12;
    let timeLeft = DURATION;
    let timerInterval = null;
    let isComplete = false;

    const CIRCUMFERENCE = 2 * Math.PI * 60;
    const timerNumberEl = document.getElementById('timerNumber');
    const progressRingEl = document.getElementById('progressRing');
    const actionBtn = document.getElementById('actionBtn');
    const mainHeading = document.getElementById('mainHeading');

    progressRingEl.style.strokeDasharray = CIRCUMFERENCE;

    function updateDisplay() {
      timerNumberEl.textContent = Math.ceil(timeLeft);
      const offset = CIRCUMFERENCE - (timeLeft / DURATION) * CIRCUMFERENCE;
      progressRingEl.style.strokeDashoffset = offset;
    }

    function startCountdown() {
      if (isComplete || timerInterval) return;

      timerInterval = setInterval(() => {
        timeLeft -= 0.1;
        if (timeLeft <= 0) {
          timeLeft = 0;
          clearInterval(timerInterval);
          timerInterval = null;
          updateDisplay();
          onComplete();
        } else {
          updateDisplay();
        }
      }, 100);
    }

    function pauseCountdown() {
      if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
      }
    }

    function onComplete() {
      isComplete = true;
      timerNumberEl.innerHTML = `
        <svg width="45" height="45" fill="none" stroke="var(--btn-green)" stroke-width="3.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
        </svg>
      `;
      mainHeading.textContent = "Your Destination is Ready! 🎉";
      actionBtn.textContent = "PROCEED TO LINK";
      actionBtn.classList.add('ready');
      actionBtn.href = TARGET_URL;
    }

    function handleBtnClick(e) {
      if (!isComplete) {
        e.preventDefault();
      }
    }

    // Automatically pauses when user switches tabs or leaves browser, resumes when they return
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        pauseCountdown();
      } else {
        startCountdown();
      }
    });

    // Initialize countdown
    updateDisplay();
    startCountdown();
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content, status_code=200)
