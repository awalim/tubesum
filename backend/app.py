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

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    pass

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

PRODUCTION_ORIGINS = [
    "https://tubesum.com",
    "https://www.tubesum.com",
    "https://dehesa.dev",
    "https://tubesum.dehesa.dev",
    "https://tubesum-backend.up.railway.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else PRODUCTION_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
    "Reinforcement Learning": "https://en.wikipedia.org/wiki/Reinforcement_learning",
    "Machine Learning": "https://en.wikipedia.org/wiki/Machine_learning",
    "AGI": "https://en.wikipedia.org/wiki/Artificial_general_intelligence",
    "Artificial General Intelligence": "https://en.wikipedia.org/wiki/Artificial_general_intelligence",
    "Neural Network": "https://en.wikipedia.org/wiki/Artificial_neural_network",
    "Deep Learning": "https://en.wikipedia.org/wiki/Deep_learning",
    "Transformers": "https://en.wikipedia.org/wiki/Transformer_(machine_learning_model)",
    "Attention Mechanism": "https://en.wikipedia.org/wiki/Attention_(machine_learning)",
    "Fine Tuning": "https://platform.openai.com/docs/guides/fine-tuning",
    "Prompt Engineering": "https://en.wikipedia.org/wiki/Prompt_engineering",
    "Data Annotation": "https://en.wikipedia.org/wiki/Labeled_data",
    "Transfer Learning": "https://en.wikipedia.org/wiki/Transfer_learning",
    "Computer Vision": "https://en.wikipedia.org/wiki/Computer_vision",
    "Natural Language Processing": "https://en.wikipedia.org/wiki/Natural_language_processing",
    "NLP": "https://en.wikipedia.org/wiki/Natural_language_processing",
    "Generative AI": "https://en.wikipedia.org/wiki/Generative_artificial_intelligence",
    "Large Language Model": "https://en.wikipedia.org/wiki/Large_language_model",
    "OpenAI API": "https://platform.openai.com/docs/",
    "ChatGPT": "https://openai.com/index/chatgpt/",
    "GPT-4": "https://openai.com/index/gpt-4/",
    "GPT-3": "https://en.wikipedia.org/wiki/GPT-3",
    "LLaMA": "https://en.wikipedia.org/wiki/LLaMA_(language_model)",
    "Gemini": "https://deepmind.google/gemini",
    "Stable Diffusion": "https://en.wikipedia.org/wiki/Stable_diffusion",
    "Midjourney": "https://docs.midjourney.com/",
    "LangSmith": "https://docs.smith.langchain.com/",
    "Pinecone": "https://docs.pinecone.io/",
    "Weaviate": "https://weaviate.io/developers/weaviate",
    "Chroma": "https://docs.trychroma.com/",
    "FAISS": "https://github.com/facebookresearch/faiss",
    "Hugging Face": "https://huggingface.co/docs",
    "Weights & Biases": "https://docs.wandb.ai/",
    "LangServe": "https://python.langchain.com/docs/langserve/",
    "LangChain Expression Language": "https://python.langchain.com/docs/concepts/#langchain-expression-language-lcel",
    "Retrieval-Augmented Generation": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    "RAG": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    "Chain of Thought": "https://en.wikipedia.org/wiki/Chain-of-thought_prompting",
    "Few-Shot Learning": "https://en.wikipedia.org/wiki/Few-shot_learning_(machine_learning)",
    "Zero-Shot Learning": "https://en.wikipedia.org/wiki/Zero-shot_learning",
    "TensorFlow": "https://www.tensorflow.org/api_docs/",
    "PyTorch": "https://pytorch.org/docs/",
    "JAX": "https://jax.readthedocs.io/en/latest/",
    "scikit-learn": "https://scikit-learn.org/stable/",
    "pandas": "https://pandas.pydata.org/docs/",
    "NumPy": "https://numpy.org/docstable/",
    "LangChain": "https://python.langchain.com/",
    "CrewAI": "https://docs.crewai.com/",
    "AutoGen": "https://microsoft.github.io/autogen/",
    "LlamaIndex": "https://docs.llamaindex.ai/",
    "Haystack": "https://docs.haystack.deepset.ai/",
    "Job Displacement": "https://en.wikipedia.org/wiki/Technological_unemployment",
    "Data Centers": "https://en.wikipedia.org/wiki/Data_center",
    "Environmental Impact": "https://en.wikipedia.org/wiki/Environmental_impact_of_information_and_communications_technology",
    "Transparency": "https://en.wikipedia.org/wiki/Transparency_(behavior)",
    "Accountability": "https://en.wikipedia.org/wiki/Accountability",
    "Ethical AI": "https://en.wikipedia.org/wiki/Ethics_of_artificial_intelligence",
    "AI Safety": "https://en.wikipedia.org/wiki/Artificial_intelligence_safety",
    "Sam Altman": "https://en.wikipedia.org/wiki/Sam_Altman",
    "Elon Musk": "https://en.wikipedia.org/wiki/Elon_Musk",
    "Ilya Sutskever": "https://en.wikipedia.org/wiki/Ilya_Sutskever",
    "Timnit Gebru": "https://en.wikipedia.org/wiki/Timnit_Gebru",
    "Karen Hao": "https://karenhao.com",
    "Silicon Valley": "https://en.wikipedia.org/wiki/Silicon_Valley",
    "Scaling Laws": "https://en.wikipedia.org/wiki/Neural_scaling_law",
    "Data Annotation": "https://en.wikipedia.org/wiki/Labeled_data",
    "Labor Exploitation": "https://en.wikipedia.org/wiki/Exploitation_of_labour",
    "Intellectual Property": "https://en.wikipedia.org/wiki/Intellectual_property",
    "AI Regulation": "https://en.wikipedia.org/wiki/Regulation_of_artificial_intelligence",
    # General concepts
    "Jevons Paradox": "https://en.wikipedia.org/wiki/Jevons_paradox",
    "Personal Brand": "https://en.wikipedia.org/wiki/Personal_branding",
    "Entrepreneurial Thinking": "https://en.wikipedia.org/wiki/Entrepreneurship",
    "AI Infrastructure": "https://en.wikipedia.org/wiki/Computing_infrastructure",
    "Universal Basic Income": "https://en.wikipedia.org/wiki/Universal_basic_income",
    "Technological Unemployment": "https://en.wikipedia.org/wiki/Technological_unemployment",
    "Job Displacement": "https://en.wikipedia.org/wiki/Technological_unemployment",
    "Future of Work": "https://en.wikipedia.org/wiki/Future_of_work",
    "Six-Step Process": "https://en.wikipedia.org/wiki/Entrepreneurship",
    "Bottom-Up Economy": "https://en.wikipedia.org/wiki/Economic_planning",
    "Personal Storytelling": "https://en.wikipedia.org/wiki/Personal_narrative",
    "Content Creation": "https://en.wikipedia.org/wiki/Content_creator",
    "YouTube Economy": "https://en.wikipedia.org/wiki/YouTube",
    # Spanish terms
    "Inteligencia Artificial": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "Desplazamiento laboral": "https://en.wikipedia.org/wiki/Technological_unemployment",
    "Emprendimiento": "https://en.wikipedia.org/wiki/Entrepreneurship",
    "Marca personal": "https://en.wikipedia.org/wiki/Personal_branding",
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
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        transcript = transcript_list.find_transcript(['en'])
        if not transcript:
            transcript = transcript_list.find_generated_transcript(['en'])
        if transcript:
            fetched = transcript.fetch()
            return ' '.join([item.text for item in fetched.snippets])
    except Exception:
        pass
    
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


def chunk_text(text: str, max_words: int = 1000) -> list:
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

FINAL_PROMPT = """Summarize this video into structured JSON.

Video title: "{title}"

Return JSON:
{{
  "summary": "3-4 paragraph markdown summary with **bold** for key terms",
  "steps": ["Plain action text — no numbering", ...],
  "concepts": [
    {{"name": "Term", "description": "One sentence explaining THIS SPECIFIC TERM as discussed in the video", "url": "Wikipedia or official docs URL"}}
  ],
  "verdict": "One honest sentence: watch or skip?"
}}

Rules:
- concepts: 4-8 items. Description MUST explain what this term MEANS IN THE VIDEO, not a dictionary definition.
- url: Wikipedia or official docs. Empty string if no good source.
- Language: {language}

Transcript excerpts:
{text}"""

SINGLE_PROMPT = """Analyze this transcript and create a structured summary.

TRANSCRIPT:
{text}

Video title: "{title}"

Generate JSON with these EXACT keys:

{{
  "summary": "Multi-paragraph markdown summary with **bold** for key terms from the transcript.",
  "steps": [
    {{"idea": "The surface claim or commonly held belief", "reality": "What the transcript actually reveals"}},
    ...
  ],
  "concepts": [
    {{"name": "Term", "description": "What this term MEANS based on the TRANSCRIPT with specific examples", "url": "Wikipedia or official docs URL"}}
  ],
  "verdict": "First, state WHAT THE VIDEO IS ABOUT in 1-2 sentences. Then give the recommendation in 1 sentence. Format: 'This video is about [essence]. [Recommendation].'"
}}

IMPORTANT:
- verdict: Start with 'This video is about...' to give context, not just 'Yes' or 'No'
- Language: {language}
- concepts: URL is REQUIRED if Wikipedia or docs exist. Use en.wikipedia.org/wiki/Page_Name format.
- summary: Use **bold** for key terms
- steps: 4-8 items, "idea" vs "reality" format"""

FINAL_PROMPT = """Analyze these transcript excerpts and create a structured summary.

TRANSCRIPT:
{text}

Video title: "{title}"

Generate JSON with these EXACT keys:

{{
  "summary": "Multi-paragraph markdown summary with **bold** for key terms from the transcript.",
  "steps": [
    {{"idea": "The surface claim or commonly held belief", "reality": "What the transcript actually reveals"}},
    ...
  ],
  "concepts": [
    {{"name": "Term", "description": "What this term MEANS based on the TRANSCRIPT with specific examples", "url": "Wikipedia or official docs URL"}}
  ],
  "verdict": "First, state WHAT THE VIDEO IS ABOUT in 1-2 sentences. Then give the recommendation in 1 sentence. Format: 'This video is about [essence]. [Recommendation].'"
}}

IMPORTANT:
- verdict: Start with 'This video is about...' to give context, not just 'Yes' or 'No'
- Language: {language}
- concepts: URL is REQUIRED if Wikipedia or docs exist. Use en.wikipedia.org/wiki/Page_Name format.
- summary: Use **bold** for key terms
- steps: 4-8 items, "idea" vs "reality" format"""

# ── Summarization engine ───────────────────────────────────────────────────────

def call_chat(client, model, system, user, json_mode=False):
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,  # Higher for more creative, contextual output
        max_tokens=4000 if json_mode else 600,
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
    """Clean steps. Supports old string format or new {idea, reality} format."""
    cleaned = []
    for step in raw_steps:
        if isinstance(step, dict) and "idea" in step and "reality" in step:
            cleaned.append({"idea": step["idea"], "reality": step["reality"]})
        elif isinstance(step, str):
            step = re.sub(r'^(Step\s*\d+\s*[:.\-–]\s*|\d+\s*[.):\-–]\s*)', '', step, flags=re.IGNORECASE).strip()
            if step:
                cleaned.append(step)
    return cleaned


def run_summarization(provider, api_key, model, full_transcript, language, title):
    effective_model = model or PROVIDER_CONFIG.get(provider, {}).get("default_model", "gpt-4o-mini")

    if provider == "claude":
        chunks = chunk_text(full_transcript, max_words=800)
        transcript_for_summary = full_transcript[:15000]
        lang_instruction = "Respond in the same language as the transcript." if language else "Return only valid JSON."
        if len(chunks) <= 2:
            raw = summarize_with_claude(api_key, effective_model,
                SINGLE_PROMPT.format(text=transcript_for_summary, language=language, title=title),
                f"You are a structured content summarizer. {lang_instruction}")
            result = safe_parse_json(raw)
        else:
            chunk_summaries = [summarize_with_claude(api_key, effective_model, CHUNK_PROMPT.format(text=c), "You are a concise summarizer.") for c in chunks]
            raw = summarize_with_claude(api_key, effective_model,
                FINAL_PROMPT.format(text="\n\n".join(chunk_summaries), language=language, title=title),
                f"You are a structured content summarizer. {lang_instruction}")
            result = safe_parse_json(raw)
        result["concepts"] = enrich_concepts_batch(effective_model, chunks if len(chunks) > 2 else [transcript_for_summary], result.get("concepts", []), title, api_key)
        return result

    client = build_client(provider, api_key)
    chunks = chunk_text(full_transcript, max_words=800)
    transcript_for_summary = full_transcript[:15000]
    lang_instruction = "Respond in the same language as the transcript." if language else "Always return valid JSON."
    
    if len(chunks) <= 2:
        raw = call_chat(client, effective_model,
            f"You are a structured content summarizer. {lang_instruction}",
            SINGLE_PROMPT.format(text=transcript_for_summary, language=language, title=title),
            json_mode=True)
        result = safe_parse_json(raw)
    else:
        chunk_summaries = [call_chat(client, effective_model, "You are a concise summarizer.", CHUNK_PROMPT.format(text=c)) for c in chunks]
        raw = call_chat(client, effective_model,
            f"You are a structured content summarizer. {lang_instruction}",
            FINAL_PROMPT.format(text="\n\n".join(chunk_summaries), language=language, title=title),
            json_mode=True)
        result = safe_parse_json(raw)
    result["concepts"] = enrich_concepts_batch(effective_model, chunks if len(chunks) > 2 else [transcript_for_summary], result.get("concepts", []), title, api_key)
    return result


def enrich_concepts_batch(model, transcript_chunks, existing_concepts, title, api_key):
    """Enrich concepts with descriptions using transcript context."""
    unique_names = [c["name"] if isinstance(c, dict) else str(c) for c in existing_concepts]
    unique_names = list(dict.fromkeys(unique_names))[:10]
    if not unique_names:
        return []
    
    combined = "\n\n".join(transcript_chunks)[:6000]
    
    if api_key:
        client = build_client("openai", api_key)
        enrich_prompt = (
            "Based on the TRANSCRIPT below, write descriptions for these concepts.\n\n"
            "TRANSCRIPT:\n" + combined[:4000] + "\n\n"
            "Concepts to describe: " + ", ".join(unique_names) + "\n\n"
            'Output JSON: [{"name":"X","description":"what this means from transcript context","url":"URL or empty"}]\n\n'
            "IMPORTANT: Write descriptions based on WHAT THE TRANSCRIPT SAYS about each term, not generic definitions."
        )
        try:
            msg = client.chat.completions.create(model=model, messages=[{"role": "user", "content": enrich_prompt}], max_tokens=800, temperature=0.3)
            raw = msg.choices[0].message.content.strip()
            enriched = safe_parse_json(raw)
            if isinstance(enriched, list) and len(enriched) > 0:
                for item in enriched:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        if not item.get("url"):
                            item["url"] = enrich_concept(name) or enrich_concept(name.lower()) or ""
                        if not item.get("description") and name in unique_names:
                            item["description"] = f"Concept from this transcript about {title}"
                return enriched
        except Exception as e:
            print(f"Enrichment error: {e}")
    
    return [{"name": n, "description": f"Mentioned in this video", "url": enrich_concept(n) or enrich_concept(n.lower()) or ""} for n in unique_names]


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

def enrich_concept(concept_name: str, video_title: str = "") -> str:
    """Get Wikipedia URL for a concept. Checks KNOWN_DOCS first, then Wikipedia API search."""
    if not concept_name:
        return ""
    
    name_lower = concept_name.strip()
    
    # 1. Check KNOWN_DOCS (exact and case-insensitive)
    if name_lower in KNOWN_DOCS:
        return KNOWN_DOCS[name_lower]
    for key in KNOWN_DOCS:
        if key.lower() == name_lower.lower():
            return KNOWN_DOCS[key]
    
    # 2. Search Wikipedia API
    wiki_url = wikipedia_search(name_lower)
    if wiki_url:
        return wiki_url
    
    return ""


def wikipedia_search(term: str) -> str:
    """Search Wikipedia API for a term and return the best matching URL."""
    try:
        import urllib.parse
        search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(term)}&limit=1&format=json"
        req = urllib.request.Request(search_url, headers={"User-Agent": "TubeSum/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data and len(data) >= 2 and data[1]:
                title = data[1][0]
                return f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    except Exception:
        pass
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
