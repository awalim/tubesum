TubeSum – Handover & Technical Summary
1. Overview

TubeSum is a YouTube summarisation tool that:

    Extracts video transcripts

    Uses AI (OpenAI, Groq, Claude, etc.) to generate summaries, step‑by‑step guides, and key concepts

    Has a full user authentication system (register, login, password reset, password change)

    Supports free tier (3 summaries/day) and a Pro plan via Lemon Squeezy

    Is deployed on Railway (backend) and Vercel (frontend)

2. What Works ✅
Feature	Status
User registration & login	✅ Fully functional
Session management (tokens)	✅ Works
Password reset & change emails	✅ Sends via Brevo (welcome, reset, changed)
Email templates (logo + gradient text)	✅ Correct – “Tube” gradient, “Sum” white
Frontend summarisation UI	✅ Loads, sends requests
AI provider configuration (UI)	✅ Users can select provider & enter API key
Transcript extraction (direct)	❌ Blocked by YouTube on Railway IPs
Summarisation using API keys	✅ Works when transcript is available
Pro checkout (Lemon Squeezy)	✅ Tested – redirects correctly
GDPR account deletion	✅ Works
History (localStorage)	✅ Works
3. What Does NOT Work ❌
3.1 Transcript Extraction – The Main Block

    Problem: YouTube blocks all Railway IP addresses (cloud provider).

    Error: Could not get transcript: YouTube is blocking requests from your IP

    Attempted fixes that failed:

        Using youtube-transcript-api with proxies= argument (requires version ≥1.2.4 – but Railway kept installing 1.2.3 despite correct requirements.txt)

        WebshareProxyConfig (incompatible with proxy URL format)

        yt-dlp (still blocked by Railway IPs without a proxy)

        Rotating proxies from a list (library version mismatch and syntax errors)

    Current state: Summarisation is impossible for any video because the transcript cannot be fetched.

3.2 Password Reset UI (Frontend)

    The reset password modal works when a token is present, but the registration form in the UI disappeared after recent changes.

    Users can still register via curl, but the frontend modal does not open (openAuthModal is not defined).

3.3 AI Prompt Quality (Partial)

    Key concepts sometimes receive irrelevant URLs (e.g., “Rebirth” linking to a gaming site).

    The improved prompt (asking for contextual description and optional URL) is in place but needs testing once transcripts work.

4. The Goal – Summarisation Quality We Want

Once transcripts are accessible, the AI should produce:
4.1 Summary

    3–4 paragraph markdown, bold for important terms.

    Focus on actionable insights, not just description.

4.2 Step‑by‑Step Instructions

    Plain action sentences, no numbering (frontend adds numbers).

    Verbs first: “Open X”, “Click Y”, “Type Z”.

    No markdown inside steps.

4.3 Key Concepts

    Name: exact term used in the video

    Description: one sentence explaining the concept in the context of the video

    URL: only included if the AI is certain (e.g., Wikipedia for “Edgar Cayce”, official docs for “LangGraph”). Empty string otherwise.

    No random links to irrelevant sites.

4.4 Verdict

    One honest sentence: “Should someone watch this and why?”

5. What Must Be Fixed (Priority Order)
Priority	Task	Description
1	Transcript extraction	Must use working residential proxies (e.g., BrightData, Oxylabs, or a fixed list with a compatible library). The current youtube-transcript-api + proxy approach must be replaced or fixed with a reliable method.
2	Frontend auth modal	Restore openAuthModal and openResetPasswordModal functions. Ensure the “Sign up free” button opens the registration form.
3	Clean up proxy code	Remove all half‑implemented proxy code and either implement a clean, tested solution or move backend to a VPS with a clean IP.
4	Improve AI prompt further	After transcripts work, test the prompt with various video types and fine‑tune the concept URL logic (maybe add a post‑processing dictionary for known terms).
6. Technical Debt & Lessons Learned

    Railway IPs are banned by YouTube – never rely on cloud provider IPs for scraping.

    youtube-transcript-api version hell – pinning ==1.2.4 did not guarantee installation; Railway’s cache caused repeated failures.

    Proxy integration is messy – the library’s proxies argument and WebshareProxyConfig are poorly documented and version‑sensitive.

    Frontend modal functions became undefined – likely due to a JavaScript error earlier in the script (e.g., FREE_DAILY_LIMIT not defined when doRegister runs).

7. Recommended Next Steps (For the Next Developer)

    Test summarisation locally with a working proxy or a VPS to confirm the AI prompt quality.

    Replace transcript extraction with either:

        A dedicated microservice that uses a rotating residential proxy pool (e.g., scrapy‑rotating‑proxies + yt‑dlp)

        Move the entire backend to a VPS with a clean residential IP (simplest).

    Fix the frontend modal – move FREE_DAILY_LIMIT definition to the top of the script and ensure all modal functions are attached to window.

    Remove dead proxy code from app.py and environment variables.

    Document the working setup – once stable, write a clear PROXY_SETUP.md for future reference.

8. Files That Contain the Most Critical Code
File	Path	Purpose
backend/app.py	/backend/app.py	Main API, summarisation, transcript extraction, proxy attempts
backend/email_utils.py	/backend/email_utils.py	Email templates (welcome, reset, changed)
frontend/index.html	/frontend/index.html	Single‑page frontend with auth, summarisation UI, modals
backend/requirements.txt	/backend/requirements.txt	Dependencies – currently broken for transcript extraction
backend/railway.toml	/railway.toml	Build & deploy config for Railway
9. Conclusion

The product is 80% complete – authentication, email, payments, and frontend work. The only thing stopping launch is transcript extraction. Once that is fixed (by using a reliable proxy service or moving to a VPS), the summarisation will work and the AI prompts can be fine‑tuned.

The user is exhausted and frustrated. A fresh pair of eyes with a clean, tested proxy implementation is urgently needed.

Handover prepared on 23 April 2026.

