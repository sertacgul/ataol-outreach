"""
Follow-up email system for ATAOL AI Techs dual-platform outreach.
- 1st follow-up: 4 days after initial email sent, no reply
- 2nd follow-up: 7 days after initial email sent, no reply
"""

import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from database import get_db, log_activity
from config import Config
from pipeline.analyzer import parse_json_response
from localization import get_language, get_language_name

client = genai.Client(api_key=Config.GEMINI_API_KEY)

FOLLOWUP_SCHEDULE = [
    {"day": 4, "number": 1},
    {"day": 7, "number": 2},
]

FOLLOWUP_PROMPT_TR = """Daha once ATAOL AI Techs adina gonderilen bir is gelistirme e-postasina yanit alinmadi. Kisa bir follow-up e-postasi yaz.

ATAOL AI Techs iki platform sunar: StrategyThrust (stratejik analiz) ve ActLedger (performans yonetimi, 7800+ KPI).

Kurallar:
- McKinsey kurumsal ciddiyetinde ton
- Onceki maili referans al ama tekrar etme
- {followup_detail}
- Maksimum 60 kelime
- Kibar ama kararlı ton
- ASLA "AI", "yapay zeka" gibi ifadeler KULLANMA
- Em-dash veya en-dash KULLANMA

SADECE gecerli JSON (markdown yok):
{{"subject": "Re: [onceki konu]", "body_html": "<p>...</p>", "body_text": "..."}}"""

FOLLOWUP_PROMPT_EN = """A previous business development email from ATAOL AI Techs received no reply. Write a brief follow-up.

ATAOL AI Techs offers two platforms: StrategyThrust (strategic analysis) and ActLedger (performance management, 7800+ KPIs).

Rules:
- McKinsey-level corporate tone
- Reference the previous email but don't repeat it
- {followup_detail}
- Maximum 60 words
- Polite but assertive
- NEVER use "AI", "artificial intelligence" or any AI reference
- No em-dashes or en-dashes
- Add at the end: "Note: All meetings and communications will be conducted in English."

Respond ONLY in valid JSON (no markdown):
{{"subject": "Re: [previous subject]", "body_html": "<p>...</p>", "body_text": "..."}}"""

FOLLOWUP_DETAILS = {
    1: {
        "tr": "Bu birinci hatirlatma. Onceki mailde vurgulanan platformun (StrategyThrust veya ActLedger) diger acisini sun. Yeni bir deger onerisi ekle.",
        "en": "This is the first follow-up. Present the other platform angle (StrategyThrust or ActLedger) from the previous email. Add a new value proposition.",
    },
    2: {
        "tr": "Bu son hatirlatma. ActLedger kampanyasini hatirlat (3 ay+1 ucretsiz veya yillik %15 indirim). Aciliyet hissi yarat ama saygili kal. Belirli bir tarih/saat onererek toplanti talebi yap.",
        "en": "This is the final follow-up. Mention ActLedger promotion (3-month +1 free or annual 15% discount). Create urgency while remaining respectful. Suggest a specific date/time for a call.",
    },
}


def generate_followup(original_email, lead, followup_number, lang_code):
    lang_name = get_language_name(lead.get("country", "INT") or "INT")
    detail_key = "tr" if lang_code == "tr" else "en"
    followup_detail = FOLLOWUP_DETAILS.get(followup_number, FOLLOWUP_DETAILS[1])[detail_key]

    if lang_code == "tr":
        system = FOLLOWUP_PROMPT_TR.format(followup_detail=followup_detail)
    elif lang_code == "en":
        system = FOLLOWUP_PROMPT_EN.format(followup_detail=followup_detail)
    else:
        system = f"""Write a brief follow-up email in {lang_name} for ATAOL AI Techs. A previous business development email received no reply.
ATAOL AI Techs offers: StrategyThrust (strategic analysis) + ActLedger (performance management, 7800+ KPIs).
McKinsey-level corporate tone. {FOLLOWUP_DETAILS.get(followup_number, FOLLOWUP_DETAILS[1])['en']}
Maximum 60 words. No AI references. No em-dashes.
Add at the end: "Note: All meetings and communications will be conducted in English."
Respond ONLY in valid JSON: {{"subject": "Re: [previous subject]", "body_html": "<p>...</p>", "body_text": "..."}}"""

    user_content = f"""Onceki mail bilgileri:
Sirket: {lead.get('company_name', '')}
Onceki konu: {original_email['subject']}
Onceki mail ozeti: {original_email['body_text'][:200]}
Kisi: {lead.get('decision_maker', '')}
Follow-up #{followup_number}

Bu bilgilere gore {lang_name} dilinde follow-up e-postasi olustur."""

    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=4096,
        ),
    )

    email_data = parse_json_response(response.text)
    if not email_data:
        return {"error": "Could not parse follow-up response", "raw": response.text}

    return email_data


def create_pending_followups():
    db = get_db()
    now = datetime.utcnow()
    created = 0

    for schedule in FOLLOWUP_SCHEDULE:
        days = schedule["day"]
        fu_number = schedule["number"]
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        sent_emails = db.execute(
            """SELECT e.*, l.company_name, l.country, l.decision_maker, l.pain_points, l.service_match,
                      l.industry, l.company_size, l.company_summary
               FROM emails e
               LEFT JOIN leads l ON e.lead_id = l.id
               WHERE e.status = 'sent'
                 AND e.email_type = CASE WHEN ? = 1 THEN 'initial' ELSE 'followup_1' END
                 AND e.sent_at <= ?
                 AND e.id NOT IN (
                     SELECT parent_email_id FROM emails
                     WHERE parent_email_id IS NOT NULL AND email_type = ?
                 )
               ORDER BY e.sent_at ASC LIMIT 20""",
            (fu_number, cutoff, f"followup_{fu_number}"),
        ).fetchall()

        for email_row in sent_emails:
            email = dict(email_row)
            lang_code = email.get("language", "en") or "en"
            lead = email

            print(f"Creating follow-up #{fu_number} for: {email['company_name']} ({email['to_email']})")

            fu_data = generate_followup(email, lead, fu_number, lang_code)
            if fu_data.get("error"):
                print(f"  Failed: {fu_data['error']}")
                continue

            from pipeline.email_generator import get_localized_footer
            footer_html, footer_text = get_localized_footer(lang_code)

            db.execute(
                """INSERT INTO emails (lead_id, subject, body_html, body_text, language, to_email, to_name,
                   from_email, status, model_used, email_type, followup_count, parent_email_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, ?)""",
                (
                    email["lead_id"],
                    fu_data.get("subject", ""),
                    fu_data.get("body_html", "") + footer_html,
                    fu_data.get("body_text", "") + footer_text,
                    lang_code,
                    email["to_email"],
                    email["to_name"],
                    email["from_email"],
                    Config.GEMINI_MODEL,
                    f"followup_{fu_number}",
                    fu_number,
                    email["id"],
                ),
            )
            db.commit()
            log_activity(db, f"followup_{fu_number}_created", "email", email["id"],
                         f"To: {email['to_email']}")
            created += 1
            print(f"  Follow-up #{fu_number} created.")

    db.close()
    print(f"\nCreated {created} follow-up emails.")
    return created


if __name__ == "__main__":
    print("=== ATAOL AI Techs Follow-up Generator ===\n")
    create_pending_followups()
