# TubeSum ⚡

> Transform any YouTube video into a structured summary, step-by-step guide, and key concepts — in seconds.

**Built by [Andrea Demaria](https://www.linkedin.com/in/andrea-d-demaria/) as a real-world AI project during her MSc in AI Business & Innovation.**

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

---

## Multi-provider AI support

Choose your AI backend — all stored safely in your browser, never on our servers:

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
| Pro | Unlimited | €4/month via Stripe |

---

## Tech stack

- **Backend**: Python · FastAPI · SQLite · Stripe
- **Frontend**: Vanilla JS · HTML/CSS (no framework — fast, portable)
- **AI**: OpenAI SDK (compatible with Groq, DeepSeek, Together, OpenRouter, Ollama)
- **Auth**: Session tokens · bcrypt-style password hashing

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
cp .env.example .env   # fill in Stripe keys if you want payments
uvicorn app:app --reload

# 3. Frontend (new terminal)
cd ../frontend
python3 -m http.server 3000
# → open http://localhost:3000
```

---

## Payment setup — Lemon Squeezy

**Why Lemon Squeezy instead of Stripe?** Lemon Squeezy is a [Merchant of Record](https://www.lemonsqueezy.com/help/what-is-a-merchant-of-record) — they are the legal seller, handle EU VAT automatically, and issue invoices to customers. You receive creator payouts. No company registration or VAT number required to start collecting payments.

1. Sign up free at [lemonsqueezy.com](https://lemonsqueezy.com)
2. Create a store → create a **subscription product** (€4/month) → copy the variant ID
3. Go to Settings → API → create an API key
4. Go to Settings → Webhooks → add your webhook URL → copy the signing secret
5. Add to your `.env`:
   ```
   LS_API_KEY=your_key
   LS_WEBHOOK_SECRET=your_secret
   LS_STORE_ID=your_store_id
   LS_PRO_VARIANT_ID=your_variant_id
   APP_DOMAIN=https://your-domain.com
   ```
6. Webhook events to enable: `order_created`, `subscription_cancelled`, `subscription_expired`

---

## Project structure

```
tubesum/
├── backend/
│   ├── app.py          # FastAPI routes (auth, payments, summarisation)
│   ├── database.py     # SQLite user DB (auth, usage, tiers)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html      # Single-page app
│   └── logo_tubesum.png
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
- ⚡ [Go Pro](http://localhost:3000) — €4/month, unlimited summaries
- 🔗 [LinkedIn](https://www.linkedin.com/in/andrea-d-demaria/) — I'm open to AI/ops roles

---

## License

MIT — free to use, fork, and build on.
