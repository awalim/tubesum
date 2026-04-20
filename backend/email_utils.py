"""
SMTP email sending for TubeSum transactional emails.

Sends welcome, password-reset, and password-changed emails via SMTP.
Uses stdlib smtplib + email.mime. Non-blocking via threading.Thread.

Env vars (see .env.example):
    SMTP_HOST
    SMTP_PORT (default 587)
    SMTP_USER
    SMTP_PASS

If SMTP_HOST is not set, send_email() logs a warning and no-ops,
so local dev does not crash.
"""
import os
import smtplib
import logging
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

logger = logging.getLogger(__name__)

# ── Email addresses (aliases configured at the domain level) ──────────────────
WELCOME_FROM       = "tubesum@dehesa.dev"
NOREPLY_FROM       = "noreply@dehesa.dev"
WELCOME_FROM_NAME  = "TubeSum"
NOREPLY_FROM_NAME  = "TubeSum"


# ══════════════════════════════════════════════════════════════════════════════
# Low-level SMTP
# ══════════════════════════════════════════════════════════════════════════════

def _smtp_config():
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "")
    return host, port, user, password


def _send_sync(to: str, subject: str, html_body: str, from_addr: str, from_name: str):
    host, port, user, password = _smtp_config()
    if not host:
        logger.warning("SMTP_HOST not set — skipping email to %s (subject: %s)", to, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                # Server doesn't support STARTTLS; continue plain (rare).
                pass
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())
        logger.info("Email sent to %s (subject: %s)", to, subject)
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to, e)


def send_email(to: str, subject: str, html_body: str,
               from_addr: str = NOREPLY_FROM, from_name: str = NOREPLY_FROM_NAME):
    """
    Send an HTML email asynchronously (fires a background thread).
    Safe to call from within FastAPI request handlers — does not block the response.
    """
    t = threading.Thread(
        target=_send_sync,
        args=(to, subject, html_body, from_addr, from_name),
        daemon=True,
    )
    t.start()


# ══════════════════════════════════════════════════════════════════════════════
# Templates (inner HTML of .email-preview from tubesum_email_templates.html)
# ══════════════════════════════════════════════════════════════════════════════

WELCOME_HTML = """\
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;">
  <tr>
    <td align="center" style="padding:40px 32px 28px;">
      <img src="https://tubesum.dehesa.dev/logo_tubesum.png" width="64" height="64" alt="TubeSum" style="display:block;margin:0 auto 14px;border-radius:50%;">
      <p style="margin:0;font-size:26px;font-weight:700;letter-spacing:-0.02em;line-height:1;"><span style="color:#ffffff;">Tube</span><span style="background:linear-gradient(135deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">Sum</span></p>
    </td>
  </tr>
  <tr>
    <td style="background:#1a1a1a;padding:32px 36px 28px;">
      <p style="margin:0 0 6px;font-size:11px;color:#ec4899;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Welcome aboard</p>
      <h1 style="margin:0 0 20px;font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">Hey <span style="color:#ec4899;">{username}</span>, you're in ⚡</h1>
      <p style="margin:0 0 16px;font-size:15px;color:#a0a0a0;line-height:1.7;">TubeSum turns any YouTube video into a clean summary, step-by-step guide, and key concepts — in seconds.</p>
      <p style="margin:0 0 28px;font-size:15px;color:#a0a0a0;line-height:1.7;">Your free plan gives you <strong style="color:#ffffff;">3 summaries per day</strong>. Paste a URL and go.</p>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;">
        <tr>
          <td style="border-radius:10px;background:linear-gradient(135deg,#8b5cf6,#ec4899);">
            <a href="https://tubesum.dehesa.dev" style="display:inline-block;padding:14px 36px;font-size:14px;font-weight:700;color:#fff;text-decoration:none;letter-spacing:0.01em;">Open TubeSum →</a>
          </td>
        </tr>
      </table>
      <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;"><tr><td style="border-top:1px solid #333;font-size:0;line-height:0;">&nbsp;</td></tr></table>
      <p style="margin:0;font-size:12px;color:#555;line-height:1.7;">Works with OpenAI, Claude, Groq, DeepSeek, OpenRouter and more. Bring your own API key or upgrade to Pro for unlimited summaries with any provider.</p>
    </td>
  </tr>
  <tr>
    <td style="background:#0f0f0f;padding:18px 36px;border-top:1px solid #222;">
      <p style="margin:0;font-size:11px;color:#444;font-family:monospace;line-height:1.8;">You received this because you signed up at tubesum.dehesa.dev<br><a href="#" style="color:#444;text-decoration:none;">Unsubscribe</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://dehesa.dev" style="color:#444;text-decoration:none;">Dehesa Studio</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://dehesa.dev/privacy" style="color:#444;text-decoration:none;">Privacy Policy</a></p>
    </td>
  </tr>
</table>
"""


PASSWORD_RESET_HTML = """\
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;">
  <tr>
    <td align="center" style="padding:40px 32px 28px;">
      <img src="https://tubesum.dehesa.dev/logo_tubesum.png" width="64" height="64" alt="TubeSum" style="display:block;margin:0 auto 14px;border-radius:50%;">
      <p style="margin:0;font-size:26px;font-weight:700;letter-spacing:-0.02em;line-height:1;"><span style="color:#ffffff;">Tube</span><span style="background:linear-gradient(135deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">Sum</span></p>
    </td>
  </tr>
  <tr>
    <td style="background:#1a1a1a;padding:32px 36px 28px;">
      <p style="margin:0 0 6px;font-size:11px;color:#a0a0a0;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Account security</p>
      <h1 style="margin:0 0 20px;font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">Password reset request</h1>
      <p style="margin:0 0 16px;font-size:15px;color:#a0a0a0;line-height:1.7;">We received a request to reset the password for <span style="color:#ffffff;">{user_email}</span>.</p>
      <p style="margin:0 0 28px;font-size:13px;color:#555;line-height:1.6;">This link expires in <strong style="color:#ffffff;">1 hour</strong>. If you didn't request this, you can safely ignore this email — nothing has changed on your account.</p>
      <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
        <tr>
          <td style="border-radius:10px;background:linear-gradient(135deg,#8b5cf6,#ec4899);">
            <a href="{reset_url}" style="display:inline-block;padding:14px 36px;font-size:14px;font-weight:700;color:#fff;text-decoration:none;">Reset Password →</a>
          </td>
        </tr>
      </table>
      <p style="margin:0;font-size:11px;color:#444;word-break:break-all;font-family:monospace;line-height:1.6;">Or copy this link:<br><span style="color:#555;">{reset_url}</span></p>
    </td>
  </tr>
  <tr>
    <td style="background:#0f0f0f;padding:18px 36px;border-top:1px solid #222;">
      <p style="margin:0;font-size:11px;color:#444;font-family:monospace;line-height:1.8;">If you didn't request this, your account is safe. No changes were made.<br><a href="https://dehesa.dev" style="color:#444;text-decoration:none;">Dehesa Studio</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://dehesa.dev/privacy" style="color:#444;text-decoration:none;">Privacy Policy</a></p>
    </td>
  </tr>
</table>
"""


PASSWORD_CHANGED_HTML = """\
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f0f;">
  <tr>
    <td align="center" style="padding:40px 32px 28px;">
      <img src="https://tubesum.dehesa.dev/logo_tubesum.png" width="64" height="64" alt="TubeSum" style="display:block;margin:0 auto 14px;border-radius:50%;">
      <p style="margin:0;font-size:26px;font-weight:700;letter-spacing:-0.02em;line-height:1;"><span style="color:#ffffff;">Tube</span><span style="background:linear-gradient(135deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">Sum</span></p>
    </td>
  </tr>
  <tr>
    <td style="background:#1a1a1a;padding:32px 36px 28px;">
      <p style="margin:0 0 6px;font-size:11px;color:#a0a0a0;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;">Account security</p>
      <h1 style="margin:0 0 20px;font-size:22px;font-weight:700;color:#ffffff;line-height:1.3;">Password changed successfully</h1>
      <p style="margin:0 0 16px;font-size:15px;color:#a0a0a0;line-height:1.7;">Your TubeSum password was updated on <strong style="color:#ffffff;">{datetime_str}</strong>.</p>
      <p style="margin:0 0 28px;font-size:15px;color:#a0a0a0;line-height:1.7;">If you made this change, you're all set. If this was <strong style="color:#ef4444;">not you</strong>, contact us immediately so we can secure your account.</p>
      <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="background:#2a2a2a;border-radius:10px;border:1px solid #333;">
            <a href="mailto:support@dehesa.dev?subject=Unauthorized+password+change+%E2%80%94+TubeSum" style="display:inline-block;padding:14px 36px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">Contact Support →</a>
          </td>
        </tr>
      </table>
    </td>
  </tr>
  <tr>
    <td style="background:#0f0f0f;padding:18px 36px;border-top:1px solid #222;">
      <p style="margin:0;font-size:11px;color:#444;font-family:monospace;line-height:1.8;">TubeSum · <a href="https://dehesa.dev" style="color:#444;text-decoration:none;">Dehesa Studio</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="https://dehesa.dev/privacy" style="color:#444;text-decoration:none;">Privacy Policy</a></p>
    </td>
  </tr>
</table>
"""


# ══════════════════════════════════════════════════════════════════════════════
# High-level per-email helpers
# ══════════════════════════════════════════════════════════════════════════════

def send_welcome_email(user_email: str, username: str):
    html = WELCOME_HTML.format(username=username, user_email=user_email)
    send_email(
        to=user_email,
        subject="Welcome to TubeSum ⚡",
        html_body=html,
        from_addr=WELCOME_FROM,
        from_name=WELCOME_FROM_NAME,
    )


def send_password_reset_email(user_email: str, reset_url: str):
    html = PASSWORD_RESET_HTML.format(user_email=user_email, reset_url=reset_url)
    send_email(
        to=user_email,
        subject="Reset your TubeSum password",
        html_body=html,
        from_addr=NOREPLY_FROM,
        from_name=NOREPLY_FROM_NAME,
    )


def send_password_changed_email(user_email: str, datetime_str: str):
    html = PASSWORD_CHANGED_HTML.format(user_email=user_email, datetime_str=datetime_str)
    send_email(
        to=user_email,
        subject="Your TubeSum password was changed",
        html_body=html,
        from_addr=NOREPLY_FROM,
        from_name=NOREPLY_FROM_NAME,
    )
