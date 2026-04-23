from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import re
import os
import urllib.request
import urllib.parse
from openai import OpenAI
from dotenv import load_dotenv
import json
import hmac
import hashlib
import secrets

try:
    from yt_dlp import YoutubeDL as ytdl
except ImportError:
    raise Exception("yt-dlp not installed. Run: pip install yt-dlp")

load_dotenv()

from database import (
    create_user, verify_user, create_session, get_user_from_token,
    delete_session, can_use, increment_usage, get_daily_usage,
    upgrade_to_pro, downgrade_to_free, FREE_DAILY_LIMIT, get_user_by_id,
    get_conn, get_user_by_email, create_password_reset_token,
    get_valid_password_reset_user_id, delete_password_reset_token,
    update_user_password,
)
from email_utils import (
    send_welcome_email, send_password_reset_email, send_password_changed_email,
)

app = FastAPI(title="TubeSum API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import json
import os
import random

PROXY_LIST = json.loads(os.getenv("PROXY_LIST", "[]"))
if not PROXY_LIST:
    # Fallback to single proxy from old Webshare env vars (optional)
    ws_user = os.getenv("WEBSHARE_PROXY_USERNAME")
    ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD")
    ws_host = os.getenv("WEBSHARE_PROXY_HOST", "")
    ws_port = os.getenv("WEBSHARE_PROXY_PORT", "")
    if ws_user and ws_pass and ws_host and ws_port:
        PROXY_LIST = [f"http://{ws_user}:{ws_pass}@{ws_host}:{ws_port}"]

_proxy_index = 0

def get_next_proxy() -> str:
    global _proxy_index
    if not PROXY_LIST:
        return None
    proxy = PROXY_LIST[_proxy_index % len(PROXY_LIST)]
    _proxy_index += 1
    return proxy

# Shuffle proxy list on startup for rotation variety
random.shuffle(PROXY_LIST)

KNOWN_DOCS = {
    "LangGraph": "https://langchain-ai.github.io/langgraph/",
    "LangChain": "https://python.langchain.com/",
    "OpenAI": "https://platform.openai.com/docs/",
    "Claude": "https://docs.anthropic.com/",
    "Groq": "https://console.groq.com/docs/",
    "DeepSeek": "https://platform.deepseek.com/api-docs/",
    "Together AI": "https://docs.together.ai/",
    "OpenRouter": "https://openrouter.ai/docs",
    "React": "https://react.dev/",
    "Vue": "https://vuejs.org/guide/",
    "Angular": "https://angular.io/docs",
    "JavaScript": "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
    "TypeScript": "https://www.typescriptlang.org/docs/",
    "Python": "https://docs.python.org/3/",
    "Node.js": "https://nodejs.org/docs/",
    "Django": "https://docs.djangoproject.com/",
    "Flask": "https://flask.palletsprojects.com/",
    "FastAPI": "https://fastapi.tiangolo.com/",
    "Docker": "https://docs.docker.com/",
    "Kubernetes": "https://kubernetes.io/docs/",
    "AWS": "https://docs.aws.amazon.com/",
    "GCP": "https://cloud.google.com/docs/",
    "Azure": "https://learn.microsoft.com/en-us/azure/",
    "Stripe": "https://stripe.com/docs/",
    "PostgreSQL": "https://www.postgresql.org/docs/",
    "MongoDB": "https://www.mongodb.com/docs/",
    "Redis": "https://redis.io/docs/",
    "GraphQL": "https://graphql.org/learn/",
    "REST": "https://restfulapi.net/",
    "API": "https://www.redhat.com/en/topics/api/what-is-a-rest-api",
    "JWT": "https://jwt.io/introduction",
    "OAuth": "https://oauth.net/2/",
    "WebSocket": "https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API",
    "Git": "https://git-scm.com/doc",
    "GitHub": "https://docs.github.com/",
    "CI/CD": "https://about.gitlab.com/topics/ci-cd/",
    "Machine Learning": "https://www.ibm.com/topics/machine-learning",
    "Neural Network": "https://www.ibm.com/topics/neural-networks",
    "LLM": "https://en.wikipedia.org/wiki/Large_language_model",
    "RAG": "https://python.langchain.com/docs/concepts/#retrieval",
    "Vector Database": "https://python.langchain.com/docs/concepts/#vector-stores",
    "Embedding": "https://platform.openai.com/docs/embeddings",
}
# ── Lemon Squeezy config ──────────────────────────────────────────────────────
# Lemon Squeezy is a Merchant of Record — they handle EU VAT, invoicing, taxes.
# You receive money as a creator. No autónoma registration required to start.
LS_API_KEY            = os.getenv("LS_API_KEY", "").strip()        # from lemonsqueezy.com/settings/api
LS_WEBHOOK_SECRET     = os.getenv("LS_WEBHOOK_SECRET", "").strip()  # from webhook settings
LS_STORE_ID           = os.getenv("LS_STORE_ID", "").strip()        # your store ID
LS_PRO_VARIANT_ID     = os.getenv("LS_PRO_VARIANT_ID", "").strip()  # variant ID for €4/mo plan
APP_DOMAIN            = os.getenv("APP_DOMAIN", "http://localhost:3000").strip()

# ── Provider config ────────────────────────────────────────────────────────────
PROVIDER_CONFIG = {
    "openai":    {"base_url": None,                              "default_model": "gpt-4o-mini"},
    "groq":      {"base_url": "https://api.groq.com/openai/v1", "default_model": "llama-3.3-70b-versatile"},
    "deepseek":  {"base_url": "https://api.deepseek.com",        "default_model": "deepseek-chat"},
    "together":  {"base_url": "https://api.together.xyz/v1",     "default_model": "meta-llama/Llama-3-70b-chat-hf"},
    "openrouter":{"base_url": "https://openrouter.ai/api/v1",    "default_model": "mistralai/mistral-7b-instruct"},
    "ollama":    {"base_url": "http://localhost:11434/v1",        "default_model": "llama3"},
}

# ── Pydantic models ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class VideoRequest(BaseModel):
    url: str
    provider: str = "openai"
    api_key: str = None
    model: str = None
    language: str = "en"

class ConceptItem(BaseModel):
    name: str
    description: str
    url: str = ""

class TranscriptResponse(BaseModel):
    transcript: str
    summary: str = ""
    steps: list = []
    concepts: list = []
    title: str = ""
    verdict: str = ""
    word_count: int = 0
    read_time_minutes: int = 0

# ── Auth helpers ───────────────────────────────────────────────────────────────

def get_current_user(authorization: str = Header(default=None)):
    """Extract Bearer token and return user, or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return get_user_from_token(token)


def require_auth(authorization: str = Header(default=None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ── Core helpers ───────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)",
        r"youtube\.com\/watch\?.*?v=([^&\n?#]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def fetch_video_title(video_id: str) -> str:
    try:
        encoded_url = urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}")
        oembed_url = f"https://www.youtube.com/oembed?url={encoded_url}&format=json"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("title", f"Video {video_id}")
    except Exception:
        return f"Video {video_id}"


def extract_transcript(video_id: str) -> str:
    last_error = None
    
    # Try up to 3 different proxies
    for attempt in range(min(3, len(PROXY_LIST) if PROXY_LIST else 1)):
        ydl_opts = {
            'skipdownload': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writesubtitles': True,
            'subtitleslangs': ['en'],
            'socket_timeout': 10,
            'cookiesfrombrowser': ('firefox',),
        }
        
        proxy = get_next_proxy() if PROXY_LIST else None
        if proxy:
            ydl_opts['proxy'] = proxy
        
        try:
            with ytdl(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                
                subtitles = info.get('subtitles', {}) or info.get('automatic_captions', {})
                
                if 'en' in subtitles:
                    sub_data = subtitles['en']
                    if isinstance(sub_data, list) and len(sub_data) > 0:
                        sub_data = sub_data[0]
                        if 'data' in sub_data:
                            return sub_data['data']
                
                raise Exception("No English subtitles available for this video")
        except Exception as e:
            last_error = e
            continue
    
    raise Exception(f"Could not get transcript after {attempt+1} attempts: {last_error}")
        
import concurrent.futures

def extract_transcript_with_timeout(video_id: str, timeout: int = 30) -> str:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(extract_transcript, video_id)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise Exception("Transcript extraction timed out (proxy or YouTube issue)")
            
def clean_transcript(text: str) -> str:
    text = re.sub(r'\b(uh+|um+|you know|like,|so,|basically,|literally)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_text(text: str, max_words: int = 800) -> list:
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def build_client(provider: str, api_key: str) -> OpenAI:
    config = PROVIDER_CONFIG.get(provider, PROVIDER_CONFIG["openai"])
    base_url = config["base_url"]
    key = api_key or ("ollama" if provider == "ollama" else None)
    if base_url:
        return OpenAI(api_key=key, base_url=base_url)
    return OpenAI(api_key=key)


def summarize_with_claude(api_key: str, model: str, prompt: str, system: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model or "claude-3-haiku-20240307",
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except ImportError:
        raise Exception("anthropic package not installed. Run: pip install anthropic --break-system-packages")


# ── Prompts ────────────────────────────────────────────────────────────────────

CHUNK_PROMPT = """You are a precise summarizer. Read the following transcript excerpt and extract only valuable information.
Return a short, dense paragraph (3-5 sentences). Ignore filler and repetition.

Transcript excerpt:
{text}"""

FINAL_PROMPT = """You are an expert at summarizing YouTube videos into clear, structured content.

Video title: "{title}"

IMPORTANT: Auto-generated transcripts often mis-spell product names. Use the video title to correct them.

Return valid JSON with exactly these keys:
{{
  "summary": "3-4 paragraph markdown summary using **bold** for important terms",
  "steps": ["Plain action text — no 'Step N:' prefix, no numbering", ...],
  "concepts": [
    {{
      "name": "ExactName",
      "description": "One sentence explaining the concept IN THE CONTEXT OF THIS VIDEO.",
      "url": "Only include if you are certain it's the official or Wikipedia page. Otherwise leave empty string."
    }}
  ],
  "verdict": "One honest sentence: should someone watch this and why?"
}}

Rules:
- steps: plain action sentences. NO numbering. NO 'Step N:' prefix.
- concepts: 4-8 items. Descriptions must be contextual to the video.
- url: only for well-known people, places, or technical terms. Empty string if unsure.
- Language: {language}

Partial summaries:
{text}"""

SINGLE_PROMPT = """You are an expert at summarizing YouTube videos into clear, structured content.

Video title: "{title}"

IMPORTANT: Auto-generated transcripts often mis-spell product names. Use the video title to correct them.

Return valid JSON with exactly these keys:
{{
  "summary": "3-4 paragraph markdown summary using **bold** for important terms",
  "steps": ["Plain action text — no 'Step N:' prefix, no numbering", ...],
  "concepts": [
    {{
      "name": "ExactName",
      "description": "One sentence explaining the concept IN THE CONTEXT OF THIS VIDEO.",
      "url": "Only include if you are certain it's the official docs or Wikipedia page. Otherwise leave empty string."
    }}
  ],
  "verdict": "One honest sentence: should someone watch this and why?"
}}

Rules:
- steps: plain action sentences. NO numbering. NO 'Step N:' prefix.
- concepts: 4-8 items. Descriptions must be contextual to the video.
- url: only for well-known people, places, or technical terms (e.g., Wikipedia, official docs). Empty string if unsure.
- Language: {language}

Transcript:
{text}"""

# ── Summarization engine ───────────────────────────────────────────────────────

def call_chat(client, model, system, user, json_mode=False):
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=2000 if json_mode else 400,
    )
    if json_mode:
        try:
            kwargs["response_format"] = {"type": "json_object"}
            return client.chat.completions.create(**kwargs).choices[0].message.content.strip()
        except Exception:
            del kwargs["response_format"]
            return client.chat.completions.create(**kwargs).choices[0].message.content.strip()
    return client.chat.completions.create(**kwargs).choices[0].message.content.strip()


def safe_parse_json(raw: str) -> dict:
    raw = re.sub(r"^```json\s*|^```\s*|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def normalise_concepts(raw_concepts: list) -> list:
    result = []
    for item in raw_concepts:
        if isinstance(item, dict):
            name = item.get("name", "")
            desc = item.get("description", "")
            # Use our new enrichment function to get a smart link
            url = enrich_concept(name) if name else ""
            result.append({"name": name, "description": desc, "url": url})
        elif isinstance(item, str):
            parts = item.split(":", 1)
            name = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else item
            url = enrich_concept(name) if name else ""
            result.append({"name": name, "description": desc, "url": url})
    return result


def clean_steps(raw_steps: list) -> list:
    cleaned = []
    for step in raw_steps:
        if isinstance(step, str):
            step = re.sub(r'^(Step\s*\d+\s*[:.\-–]\s*|\d+\s*[.):\-–]\s*)', '', step, flags=re.IGNORECASE).strip()
            if step:
                cleaned.append(step)
    return cleaned


def run_summarization(provider, api_key, model, full_transcript, language, title):
    effective_model = model or PROVIDER_CONFIG.get(provider, {}).get("default_model", "gpt-4o-mini")

    if provider == "claude":
        chunks = chunk_text(full_transcript, max_words=800)
        if len(chunks) <= 2:
            raw = summarize_with_claude(api_key, effective_model,
                SINGLE_PROMPT.format(text=full_transcript[:12000], language=language, title=title),
                "You are a structured content summarizer. Return only valid JSON.")
        else:
            chunk_summaries = [summarize_with_claude(api_key, effective_model, CHUNK_PROMPT.format(text=c), "You are a concise summarizer.") for c in chunks]
            raw = summarize_with_claude(api_key, effective_model,
                FINAL_PROMPT.format(text="\n\n".join(chunk_summaries), language=language, title=title),
                "You are a structured content summarizer. Return only valid JSON.")
        return safe_parse_json(raw)

    client = build_client(provider, api_key)
    chunks = chunk_text(full_transcript, max_words=800)
    if len(chunks) <= 2:
        raw = call_chat(client, effective_model,
            "You are a structured content summarizer. Always return valid JSON.",
            SINGLE_PROMPT.format(text=full_transcript[:12000], language=language, title=title),
            json_mode=True)
    else:
        chunk_summaries = [call_chat(client, effective_model, "You are a concise summarizer.", CHUNK_PROMPT.format(text=c)) for c in chunks]
        raw = call_chat(client, effective_model,
            "You are a structured content summarizer. Always return valid JSON.",
            FINAL_PROMPT.format(text="\n\n".join(chunk_summaries), language=language, title=title),
            json_mode=True)
    return safe_parse_json(raw)


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"message": "TubeSum API"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/register")
async def register(req: RegisterRequest):   # ← remove BackgroundTasks
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = create_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered")
    token = create_session(user["id"])

    username = user["email"].split("@", 1)[0]
    send_welcome_email(user_email=user["email"], username=username)   # ← direct call

    return {
        "token": token,
        "user": {"email": user["email"], "tier": user["tier"]}
    }
    
@app.post("/auth/login")
async def login(req: LoginRequest):
    user = verify_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_session(user["id"])
    return {
        "token": token,
        "user": {"email": user["email"], "tier": user["tier"]}
    }


@app.post("/auth/logout")
async def logout(authorization: str = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        delete_session(authorization[7:])
    return {"message": "Logged out"}


@app.post("/auth/request-password-reset")
async def request_password_reset(req: PasswordResetRequest):
    print(f"🔵 PASSWORD RESET REQUEST for {req.email}", flush=True)
    user = get_user_by_email(req.email)
    if user:
        print(f"🔵 User found: {user['email']}", flush=True)
        token = secrets.token_urlsafe(32)
        create_password_reset_token(user_id=user["id"], token=token, ttl_seconds=3600)
        reset_url = f"{APP_DOMAIN}/reset-password?token={token}"
        print(f"🔵 Reset URL: {reset_url}", flush=True)
        print(f"🔵 Calling send_password_reset_email...", flush=True)
        send_password_reset_email(user_email=user["email"], reset_url=reset_url)
        print(f"🔵 send_password_reset_email returned", flush=True)
    else:
        print(f"🔵 No user found for {req.email}", flush=True)
    return {"message": "If that email is registered, a reset link has been sent."}

@app.post("/auth/reset-password")
async def reset_password(req: PasswordResetConfirm):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_id = get_valid_password_reset_user_id(req.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    update_user_password(user_id, req.new_password)
    delete_password_reset_token(req.token)

    user = get_user_by_id(user_id)
    if user:
        from datetime import datetime as _dt
        datetime_str = _dt.utcnow().strftime("%d %b %Y at %H:%M UTC")
        send_password_changed_email(user_email=user["email"], datetime_str=datetime_str)

    return {"message": "Password updated successfully."}


@app.get("/auth/me")
async def me(authorization: str = Header(default=None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    used_today = get_daily_usage(user["id"])
    return {
        "email": user["email"],
        "tier": user["tier"],
        "used_today": used_today,
        "daily_limit": None if user["tier"] == "pro" else FREE_DAILY_LIMIT,
        "remaining": None if user["tier"] == "pro" else max(0, FREE_DAILY_LIMIT - used_today),
    }


# ── Lemon Squeezy payments ────────────────────────────────────────────────────
# Lemon Squeezy is a Merchant of Record:
#   - They handle EU VAT collection and remittance
#   - They issue invoices to customers
#   - You receive creator payouts — no autónoma obligation to start

def _ls_headers():
    return {
        "Authorization": f"Bearer {LS_API_KEY}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def _ls_request(method: str, path: str, body: dict = None):
    """Make a request to the Lemon Squeezy API."""
    url = f"https://api.lemonsqueezy.com/v1/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers=_ls_headers(),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise HTTPException(
            status_code=502,
            detail=f"Lemon Squeezy error {e.code}: {error_body}"
        )

def enrich_concept(concept_name: str) -> str:
    if not concept_name:
        return ""
    name_lower = concept_name.strip()
    if name_lower in KNOWN_DOCS:
        return KNOWN_DOCS[name_lower]
    for key in KNOWN_DOCS:
        if key.lower() == name_lower.lower():
            return KNOWN_DOCS[key]
    return ""

@app.post("/payments/create-checkout")
async def create_checkout(authorization: str = Header(default=None)):
    """Create a Lemon Squeezy checkout URL for the Pro plan."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to upgrade")
    if user["tier"] == "pro":
        raise HTTPException(status_code=400, detail="Already on Pro plan")
    if not LS_API_KEY or not LS_PRO_VARIANT_ID:
        raise HTTPException(status_code=503, detail="Payment system not configured yet")

    body = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "email": user["email"],
                    "custom": {"user_id": str(user["id"])},
                },
                "product_options": {
                    "redirect_url": f"{APP_DOMAIN}?upgraded=true",
                },
            },
            "relationships": {
                "store":   {"data": {"type": "stores",   "id": str(LS_STORE_ID)}},
                "variant": {"data": {"type": "variants",  "id": str(LS_PRO_VARIANT_ID)}},
            },
        }
    }

    data = _ls_request("POST", "checkouts", body)
    checkout_url = data["data"]["attributes"]["url"]
    return {"checkout_url": checkout_url}


@app.post("/payments/webhook")
async def ls_webhook(request: Request):
    """
    Lemon Squeezy calls this on subscription events.
    Signature: X-Signature header = HMAC-SHA256(secret, raw_body), hex digest.
    """
    payload = await request.body()
    sig = request.headers.get("X-Signature", "")

    if LS_WEBHOOK_SECRET:
        expected = hmac.new(
            LS_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(payload)
    event_name = event.get("meta", {}).get("event_name", "")
    custom      = event.get("meta", {}).get("custom_data", {})
    obj         = event.get("data", {}).get("attributes", {})

    if event_name == "order_created":
        # One-time confirmation that checkout completed
        user_id = custom.get("user_id")
        if user_id:
            sub_id = str(event["data"].get("id", ""))
            customer_id = str(obj.get("customer_id", ""))
            upgrade_to_pro(
                user_id=int(user_id),
                stripe_customer_id=customer_id,      # reusing field for LS customer ID
                stripe_subscription_id=sub_id,       # reusing field for LS order/sub ID
            )

    elif event_name in ("subscription_cancelled", "subscription_expired",
                        "subscription_paused", "subscription_payment_failed"):
        sub_id = str(event["data"].get("id", ""))
        if sub_id:
            downgrade_to_free(sub_id)

    return {"status": "ok"}


@app.get("/payments/portal")
async def billing_portal(authorization: str = Header(default=None)):
    """
    Lemon Squeezy doesn't have a managed portal URL like Stripe.
    We redirect to the customer's subscription management page.
    """
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # LS customer portal is at a fixed URL per store
    portal_url = f"https://app.lemonsqueezy.com/my-orders"
    return {"portal_url": portal_url}


# ── Main transcript/summarize route ───────────────────────────────────────────

@app.post("/transcript", response_model=TranscriptResponse)
async def get_transcript(request: VideoRequest, authorization: str = Header(default=None)):
    print(f"🔵 /transcript called with URL: {request.url}", flush=True)
    print(f"🔵 Provider: {request.provider}, Model: {request.model}, Has API key: {bool(request.api_key)}", flush=True)
    
    # ── Auth & usage gate ──────────────────────────────────────────────────────
    user = get_current_user(authorization)
    if not user:
        print(f"🔴 No authenticated user", flush=True)
        raise HTTPException(status_code=401, detail="Please create a free account...")
    print(f"🔵 User: {user['email']}, Tier: {user['tier']}", flush=True)
    allowed, reason = can_use(user)
    if not allowed:
        print(f"🔴 Usage limit reached: {reason}", flush=True)
        raise HTTPException(status_code=429, detail=reason)
    print(f"🔵 Usage allowed, proceeding...", flush=True)
    
    # Then continue with transcript extraction...

    # ── Core processing ────────────────────────────────────────────────────────
    try:
        video_id = extract_video_id(request.url)
        title = fetch_video_title(video_id)
        raw_transcript = extract_transcript_with_timeout(video_id, timeout=45)
        full_transcript = clean_transcript(raw_transcript)
        word_count = len(full_transcript.split())
        read_time_minutes = max(1, word_count // 200)

        summary, steps, concepts, verdict = "", [], [], ""

        if request.api_key:
            try:
                result = run_summarization(
                    provider=request.provider,
                    api_key=request.api_key,
                    model=request.model,
                    full_transcript=full_transcript,
                    language=request.language,
                    title=title,
                )
                summary  = result.get("summary", "")
                steps    = clean_steps(result.get("steps", []))
                concepts = normalise_concepts(result.get("concepts", []))
                verdict  = result.get("verdict", "")
            except Exception as e:
                print(f"Summarization error ({request.provider}): {e}")

        # Count the usage only after successful processing
        increment_usage(user["id"])

        return TranscriptResponse(
            transcript=full_transcript,
            summary=summary,
            steps=steps,
            concepts=concepts,
            title=title,
            verdict=verdict,
            word_count=word_count,
            read_time_minutes=read_time_minutes,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── GDPR — Account deletion ────────────────────────────────────────────────────

@app.delete("/auth/account")
async def delete_account(authorization: str = Header(default=None)):
    """
    GDPR Article 17 — Right to erasure.
    Deletes all personal data associated with the account.
    Email is anonymised, password hash wiped, usage records deleted.
    """
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user["id"]
    with get_conn() as conn:
        # Delete usage records
        conn.execute("DELETE FROM usage WHERE user_id = ?", (user_id,))
        # Invalidate all sessions
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        # Anonymise user record — keep row for referential integrity but wipe PII
        conn.execute("""
            UPDATE users
            SET email = ?,
                password_hash = 'deleted',
                salt = 'deleted',
                is_active = 0,
                stripe_customer_id = NULL,
                stripe_subscription_id = NULL
            WHERE id = ?
        """, (f"deleted_{user_id}_{secrets.token_hex(4)}@deleted.invalid", user_id))

    return {"message": "Your account and all associated data have been permanently deleted."}


@app.get("/privacy")
async def privacy_redirect():
    """Redirect to privacy policy page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="https://dehesa.dev/privacy")

@app.post("/admin/clear-users")
async def clear_users():
    from database import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM password_reset_tokens")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM usage")
        conn.execute("DELETE FROM users")
    return {"message": "All users, sessions, tokens, and usage deleted."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
