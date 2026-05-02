import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from gmail_auth.auth import get_gmail_service
from config import Config
from database import get_db, log_activity


def send_notification(subject, body_html, body_text=None):
    service = get_gmail_service()

    msg = MIMEMultipart("alternative")
    msg["To"] = Config.NOTIFICATION_EMAIL
    msg["From"] = Config.GMAIL_SENDER_EMAIL
    msg["Subject"] = subject

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def notify_pending_emails(count):
    dashboard_url = f"http://localhost:{Config.FLASK_PORT}/emails/pending"

    subject = f"[ATAOL AI Techs] {count} email onay bekliyor"
    body_html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #1a1a2e;">{count} yeni outreach e-postasi onay bekliyor</h2>
        <p>ATAOL AI Techs outreach sistemi {count} adet yeni e-posta olusturdu.</p>
        <p>Onaylamak veya reddetmek icin dashboard'u ziyaret edin:</p>
        <a href="{dashboard_url}"
           style="display: inline-block; background: #1976d2; color: white; padding: 12px 24px;
                  text-decoration: none; border-radius: 6px; font-weight: 600; margin: 16px 0;">
            Dashboard'u Ac
        </a>
        <p style="color: #888; font-size: 12px; margin-top: 24px;">
            ATAOL AI Techs Outreach Otomasyon Sistemi
        </p>
    </div>
    """
    body_text = f"{count} yeni outreach e-postasi onay bekliyor.\nDashboard: {dashboard_url}"

    try:
        send_notification(subject, body_html, body_text)
        db = get_db()
        log_activity(db, "notification_sent", details=f"Pending emails: {count}")
        db.close()
        print(f"Notification sent to {Config.NOTIFICATION_EMAIL}")
    except Exception as e:
        print(f"Failed to send notification: {e}")
