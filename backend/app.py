from fastapi import FastAPI, HTTPException, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from youtube_transcript_api import YouTubeTranscriptApi
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
    try:
        # Rotating residential proxy — needed because YouTube blocks cloud IPs
        ws_user = os.getenv("WEBSHARE_PROXY_USERNAME")
        ws_pass = os.getenv("WEBSHARE_PROXY_PASSWORD")

        if ws_user and ws_pass:
            from youtube_transcript_api.proxies import WebshareProxyConfig
            api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=ws_user,
                    proxy_password=ws_pass,
                )
            )
        else:
            api = YouTubeTranscriptApi()

        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['en'])
        except Exception:
            transcripts = list(transcript_list)
            if not transcripts:
                raise Exception("No transcripts available")
            transcript = transcripts[0]
        transcript_data = transcript.fetch()
        return " ".join(
            segment.text if hasattr(segment, "text") else segment["text"]
            for segment in transcript_data
        )
    except Exception as e:
        raise Exception(f"Could not get transcript: {str(e)}")


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
  "concepts": [{{"name": "ExactName", "description": "One sentence explanation.", "url": "https://official-docs-or-empty"}}, ...],
  "verdict": "One honest sentence: should someone watch this and why?"
}}

Rules:
- steps: plain action sentences. NO numbering. NO 'Step N:' prefix.
- concepts: 4-8 items. Official doc URLs for well-known tools. Empty string if unknown.
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
  "concepts": [{{"name": "ExactName", "description": "One sentence explanation.", "url": "https://official-docs-or-empty"}}, ...],
  "verdict": "One honest sentence: should someone watch this and why?"
}}

Rules:
- steps: plain action sentences. NO numbering. NO 'Step N:' prefix.
- concepts: 4-8 items. Official doc URLs for well-known tools.
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
            result.append({"name": item.get("name",""), "description": item.get("description",""), "url": item.get("url","")})
        elif isinstance(item, str):
            parts = item.split(":", 1)
            result.append({"name": parts[0].strip(), "description": parts[1].strip() if len(parts)>1 else item, "url": ""})
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
async def register(req: RegisterRequest, background_tasks: BackgroundTasks):  # Add this parameter
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = create_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered")
    token = create_session(user["id"])

    # Queue welcome email instead of sending directly
    username = user["email"].split("@", 1)[0]
    send_welcome_email_background(background_tasks, user_email=user["email"], username=username)

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
async def request_password_reset(req: PasswordResetRequest, background_tasks: BackgroundTasks):  # Add this
    user = get_user_by_email(req.email)
    if user:
        token = secrets.token_urlsafe(32)
        create_password_reset_token(user_id=user["id"], token=token, ttl_seconds=3600)
        reset_url = f"{APP_DOMAIN}/reset-password?token={token}"
        send_password_reset_email_background(background_tasks, user_email=user["email"], reset_url=reset_url)
    return {"message": "If that email is registered, a reset link has been sent."}


@app.post("/auth/reset-password")
async def reset_password(req: PasswordResetConfirm, background_tasks: BackgroundTasks):  # Add this
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
        send_password_changed_email_background(background_tasks, user_email=user["email"], datetime_str=datetime_str)

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
    # ── Auth & usage gate ──────────────────────────────────────────────────────
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Please create a free account to use TubeSum. Free plan: 3 summaries/day."
        )
    allowed, reason = can_use(user)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=reason  # "Daily limit reached (3 summaries/day on free plan)"
        )

    # ── Core processing ────────────────────────────────────────────────────────
    try:
        video_id = extract_video_id(request.url)
        title = fetch_video_title(video_id)
        raw_transcript = extract_transcript(video_id)
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
    
@app.get("/test-email/{email}")
async def test_email(email: str, background_tasks: BackgroundTasks):
    """Test endpoint to verify email sending works - remove after testing"""
    from email_utils import send_welcome_email_background  # You'll add this function
    
    send_welcome_email_background(background_tasks, email, "TestUser")
    return {"message": f"Test email queued for {email}"}


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
