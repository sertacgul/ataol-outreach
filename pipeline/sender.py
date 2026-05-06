import base64
import time
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from gmail_auth.auth import get_gmail_service
from database import get_db, log_activity
from config import Config


def get_today_send_count(db):
    cursor = db.execute(
        "SELECT COUNT(*) c FROM daily_send_log WHERE sent_date = ?",
        (date.today().isoformat(),),
    )
    return cursor.fetchone()["c"]


def can_send_today(db):
    return get_today_send_count(db) < Config.MAX_EMAILS_PER_DAY


def send_single_email(service, email_record):
    msg = MIMEMultipart("alternative")
    msg["To"] = email_record["to_email"]
    msg["From"] = email_record["from_email"]
    msg["Subject"] = email_record["subject"]

    msg.attach(MIMEText(email_record["body_text"], "plain", "utf-8"))
    msg.attach(MIMEText(email_record["body_html"], "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return result


def send_approved_batch(db):
    from datetime import datetime

    if datetime.utcnow().weekday() >= 5:
        print("Weekend - skipping email sends.")
        return 0

    remaining = Config.MAX_EMAILS_PER_DAY - get_today_send_count(db)
    if remaining <= 0:
        print(f"Daily limit reached ({Config.MAX_EMAILS_PER_DAY} emails).")
        return 0

    approved = db.execute(
        """SELECT e.*, l.country FROM emails e
           LEFT JOIN leads l ON e.lead_id = l.id
           WHERE e.status = 'approved' ORDER BY e.approved_at ASC""",
        (),
    ).fetchall()

    if not approved:
        print("No approved emails to send.")
        return 0

    service = get_gmail_service()
    sent_count = 0

    for email_row in approved:
        if sent_count >= remaining:
            break

        email_dict = dict(email_row)
        country = email_dict.get("country", "INT") or "INT"

        print(f"Sending to: {email_dict['to_email']} ({country}) - {email_dict['subject']}")

        try:
            result = send_single_email(service, email_dict)

            db.execute(
                """UPDATE emails SET
                    status = 'sent',
                    gmail_message_id = ?,
                    gmail_thread_id = ?,
                    sent_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (result.get("id", ""), result.get("threadId", ""), email_dict["id"]),
            )
            db.execute(
                "INSERT INTO daily_send_log (email_id, sent_date) VALUES (?, ?)",
                (email_dict["id"], date.today().isoformat()),
            )
            db.commit()
            log_activity(db, "email_sent", "email", email_dict["id"], f"To: {email_dict['to_email']}")
            sent_count += 1
            print(f"  Sent successfully.")

            email_type = email_dict.get("email_type", "initial") or "initial"
            if email_type == "followup_2":
                db.execute(
                    "UPDATE leads SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (email_dict["lead_id"],),
                )
            else:
                db.execute(
                    "UPDATE leads SET status = 'contacted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (email_dict["lead_id"],),
                )
            db.commit()

        except Exception as e:
            print(f"  Failed: {e}")
            db.execute(
                "UPDATE emails SET status = 'failed' WHERE id = ?",
                (email_dict["id"],),
            )
            db.commit()
            log_activity(db, "email_send_failed", "email", email_dict["id"], str(e))

        time.sleep(3)

    print(f"Sent {sent_count}/{len(approved)} emails.")
    return sent_count


if __name__ == "__main__":
    print("=== ATAOL AI Techs Email Sender ===\n")
    db = get_db()
    send_approved_batch(db)
    db.close()
