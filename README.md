# TubeSum ⚡

> Transform any YouTube video into a structured summary, step-by-step guide, and key concepts — in seconds.

**Built by [Andrea Demaria](https://www.linkedin.com/in/andrea-d-demaria/) as a real-world AI project during her MSc in AI Business & Innovation.**
**Part of [Dehesa Studio](https://dehesa.dev) — tools that make sense of things.**

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-awalim-yellow?logo=buymeacoffee)](https://buymeacoffee.com/awalim)
[![GitHub Stars](https://img.shields.io/github/stars/awalim/tubesum?style=social)](https://github.com/awalim/tubesum)

---

## What it does

Paste a YouTube URL → get back:

- 📋 **Summary** — markdown-formatted, bold key terms, structured paragraphs
- 📌 **Step-by-step guide** — extracted process steps, no fluff
- 💡 **Key concepts** — with links to official documentation
- 🎯 **Worth watching?** — one-sentence honest verdict
- 📝 **Full transcript** — cleaned and downloadable

Works with **long videos** via chunked summarisation (8+ hour lectures handled gracefully).
Transcription errors corrected automatically using the video title.

---

## Multi-provider AI support

Choose your AI backend — keys stored safely in your browser, never on our servers:

| Provider | Type | Notes |
|---|---|---|
| ⚡ OpenAI | Paid | gpt-4o-mini, gpt-4o |
| 🧠 Claude | Paid | claude-3-haiku, claude-3-5-sonnet |
| 🔍 DeepSeek | Cheap | ~10x cheaper than OpenAI |
| 🚀 Groq | Free tier | llama-3.3-70b — extremely fast |
| 🌐 OpenRouter | Free models | 100+ models, free `:free` tier |
| 🦙 Ollama | Local | 100% private, runs on your machine |

---

## Freemium model

| Plan | Summaries | Price |
|---|---|---|
| Free | 3/day | €0 — no credit card |
| Pro | Unlimited | €4/month |

[→ Try TubeSum](https://dehesa.dev/tubesum) · [→ Go Pro](https://dehesa.lemonsqueezy.com)

---

## Tech stack

- **Backend**: Python · FastAPI · SQLite
- **Frontend**: Vanilla JS · HTML/CSS (no framework — fast, portable)
- **AI**: OpenAI SDK (compatible with Groq, DeepSeek, Together, OpenRouter, Ollama)
- **Auth**: Session tokens · secure password hashing
- **Payments**: Lemon Squeezy (Merchant of Record — handles EU VAT)

---

## Running locally

```bash
# 1. Clone
git clone https://github.com/awalim/tubesum.git
cd tubesum

# 2. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload

# 3. Frontend (new terminal)
cd ../frontend
python3 -m http.server 3000
# → open http://localhost:3000
```

The app runs fully without payment keys — you get transcript extraction and AI summarisation out of the box with your own AI provider key entered in the UI.

---

## Project structure

```
tubesum/
├── backend/
│   ├── app.py          # FastAPI routes (auth, payments, summarisation)
│   ├── database.py     # SQLite user DB (auth, usage, tiers)
│   ├── requirements.txt
│   └── .env.example    # Environment variable template
├── frontend/
│   ├── index.html      # Single-page app
│   └── logo_tubesum.png
├── landing/
│   └── index.html      # Dehesa Studio landing page
└── .github/
    └── FUNDING.yml
```

---

## ⭐ If this saved you time, a star means a lot

This project is actively maintained. Stars help it get discovered and directly support continued development.

→ [Star on GitHub](https://github.com/awalim/tubesum)

---

## Support the project

- ☕ [Buy Me a Coffee](https://buymeacoffee.com/awalim) — one-off thanks
- ⚡ [Go Pro](https://dehesa.lemonsqueezy.com) — €4/month, unlimited summaries
- 🌿 [Dehesa Studio](https://dehesa.dev) — more tools coming
- 🔗 [LinkedIn](https://www.linkedin.com/in/andrea-d-demaria/) — open to AI/ops roles in Europe

---

## License

MIT — free to use, fork, and build on.
