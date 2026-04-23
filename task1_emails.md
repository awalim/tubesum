# Task 1 — Implement transactional emails for TubeSum

## Context
TubeSum is a FastAPI backend (`backend/app.py`) with SQLite auth. Three transactional emails need to be wired up and sent via SMTP using the email aliases already configured at dehesa.dev.

## Aliases (already set up at domain level)
- `tubesum@dehesa.dev` → forwards to `apps@dehesa.dev`  — use for welcome email
- `noreply@dehesa.dev` → forwards to `apps@dehesa.dev`  — use for password reset + changed
- `support@dehesa.dev` → forwards to `hello@dehesa.dev` — used in "contact support" mailto link only

## What to implement

### 1. Email sending utility
Create `backend/email_utils.py` with a `send_email(to, subject, html_body)` function using Python's `smtplib` + `email.mime`. Read SMTP credentials from env vars:
```
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
```

### 2. Welcome email
Trigger: after successful `POST /register`  
From: `tubesum@dehesa.dev`  
Subject: `Welcome to TubeSum ⚡`  
Template variables: `{{ username }}`, `{{ user.email }}`

### 3. Password reset email
The app currently has no password reset flow. Implement it:
- `POST /request-password-reset` — accepts `{ email }`, generates a signed token (use `secrets.token_urlsafe(32)`), stores it in a new `password_reset_tokens` table with expiry (1 hour), sends the email
- `POST /reset-password` — accepts `{ token, new_password }`, validates token not expired, updates password hash, deletes token  

From: `noreply@dehesa.dev`  
Subject: `Reset your TubeSum password`  
Template variables: `{{ user.email }}`, `{{ reset_url }}` (construct as `{APP_DOMAIN}/reset-password?token={token}`)

### 4. Password changed confirmation email
Trigger: after a successful password reset (step above)  
From: `noreply@dehesa.dev`  
Subject: `Your TubeSum password was changed`  
Template variables: `{{ datetime }}` (UTC, formatted as `16 Apr 2026 at 14:32 UTC`)

## HTML templates
The HTML for all three emails is in `tubesum_email_templates.html` (the `.email-preview` div of each panel). Copy the inner HTML of each into the corresponding template string in `email_utils.py`. Replace `{{ variable }}` placeholders with Python f-string or `.format()` substitution.

## Notes
- Send emails in a background thread (`threading.Thread`) so they don't block the API response
- If `SMTP_HOST` is not set, log a warning and skip sending (don't crash in dev)
- Add the 4 new env vars to `backend/.env.example` with comments
- Add `password_reset_tokens` table creation to `database.py` alongside the existing users table init
