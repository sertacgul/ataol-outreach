import json
from google import genai
from google.genai import types
from database import get_db, log_activity
from config import Config
from pipeline.analyzer import parse_json_response

client = genai.Client(api_key=Config.GEMINI_API_KEY)

LOGO_URL = "https://sertacgul.github.io/strategythrust-dashboard/ataol-logo.png"
LINKEDIN_URL = "https://www.linkedin.com/company/ataol-ai-techs"
LINKEDIN_ICON = "https://cdn-icons-png.flaticon.com/512/174/174857.png"

ATAOL_INFO = """ATAOL AI Techs - teknoloji ve yazilim cozumleri sirketi:

Kendi platformlarimiz:
1. StrategyThrust - Stratejik Karar Destek Platformu:
- 72 saat icinde geleneksel danismanligin 3-6 aylik isini tamamlar
- Geleneksel yonetim danismanliginin yaklasik 150'de 1 fiyatina ayni kalitede cikti
- Sektor analizi, rekabet konumlandirmasi, pazar dinamikleri ve stratejik projeksiyonlar

2. ActLedger - Operasyonel Mukemmellik Sistem Platformu:
- 15 sektor, 576+ departman, 7800+ hazir KPI - dunyanin en kapsamli sektor-spesifik KPI kutuphanesi
- 5 katmanli performans olcum cercevesi (Performance, Quality, Time, Risk, AI Insight)
- Dakikalar icinde tam operasyonel cerceve kurulumu
- Saha operasyonlari, envanter, is akislari, otomasyon, IoT entegrasyonu
- Mobil-first: iOS native app + PWA
- Kampanya: 3 aylik lisans alanlara +1 ay ucretsiz | Yillik lisans alanlara %15 indirim

Kurumsal hizmetlerimiz:
- Otomasyon cozumleri, mobil uygulama gelistirme (iOS/Android), web uygulama gelistirme
- Is sureclerini dijitallestirme, ozel yazilim cozumleri

Kurucu: Sertac Gul | ataolai.tech | strategythrust.com | actledger.com"""

STRUCTURED_OUTPUT_RULES = """
Asagidaki JSON yapisinda yanit ver. HER alan hedef dilde yazilmali.
ASLA "AI", "yapay zeka", "artificial intelligence" kullanma.
72 saat ve 1/150 fiyat avantaji toplamda SADECE BIRER KEZ gecsin.
Em-dash/en-dash kullanma, sadece kisa tire (-).
McKinsey/BCG/Bain kurumsal ciddiyetinde ton.
Fiyat bilgisi verme (rakam belirtme), avantaj olarak sun.
Kampanya bilgisini (3 ay+1 ay / yillik %15) dogal bir sekilde ekle.

JSON yapisi (markdown yok, kod blogu yok):
{{
  "subject": "Konu basligi - max 60 karakter, ATAOL odakli",
  "greeting": "Sayin Ad Soyad, (veya Sayin Yetkililer,)",
  "intro": "Firmaya ozel giris paragrafi. Sirketlerini arastirdigini goster. Max 50 kelime.",
  "ataol_intro": "ATAOL AI Techs'in iki platformunu ozetleyen 1-2 cumle. Max 30 kelime.",
  "assessment_title": "Sizin icin hazirladigimiz on degerlendirme (hedef dile cevir)",
  "industry_label": "Sektor (hedef dile cevir)",
  "industry_value": "Firmanin sektoru",
  "stage_label": "Asama (hedef dile cevir)",
  "stage_value": "Firmanin asamasi",
  "employee_label": "Olcek (hedef dile cevir)",
  "employee_value": "Tahminli calisan sayisi",
  "strategic_challenges_label": "Stratejik Zorluklar (hedef dile cevir)",
  "strategic_challenges": ["Zorluk 1", "Zorluk 2"],
  "operational_challenges_label": "Operasyonel Zorluklar (hedef dile cevir)",
  "operational_challenges": ["Zorluk 1", "Zorluk 2"],
  "st_value_prop": "StrategyThrust deger onerisi. 72 saat veya 1/150 fiyattan BIRINI kullan. Max 35 kelime.",
  "st_solutions": ["Bu firmaya ozel StrategyThrust cozumu 1", "Cozum 2"],
  "al_value_prop": "ActLedger deger onerisi. Sektor-spesifik KPI avantajini vurgula. Max 35 kelime.",
  "al_solutions": ["Bu firmaya ozel ActLedger cozumu 1", "Cozum 2"],
  "innovation_highlights": ["Inovasyon/dunya ilki 1", "Inovasyon 2", "Inovasyon 3"],
  "services_note": "ATAOL'un platformlar disindaki hizmetlerini (otomasyon, mobil/web uygulama, ozel yazilim) firmaya ozel 1 cumlede bahset. Max 20 kelime.",
  "closing": "Kapanıs - kisa gorusme talebiyle biten soru. Max 30 kelime.",
  "cta_text": "Gorusme Planla (hedef dile cevir)"
}}"""

SYSTEM_PROMPT_TR = f"""Sen ATAOL AI Techs adina kurumsal is gelistirme e-postasi yaziyorsun.
{ATAOL_INFO}

HITAP: Kisi adi varsa "Sayin [Ad Soyad],", yoksa "Sayin Yetkililer,". ASLA placeholder kullanma.
{STRUCTURED_OUTPUT_RULES}"""

SYSTEM_PROMPT_EN = f"""You write corporate business development emails for ATAOL AI Techs.
{ATAOL_INFO}

GREETING: If contact name provided use "Dear [Name],", otherwise "Dear Sir/Madam,". NEVER use placeholders.
ALL field values must be in English.
{STRUCTURED_OUTPUT_RULES}"""


def get_localized_system_prompt(language, language_name, country_code):
    if language == "tr":
        return SYSTEM_PROMPT_TR
    if language == "en":
        return SYSTEM_PROMPT_EN
    return f"""You write corporate business development emails for ATAOL AI Techs.
{ATAOL_INFO}

CRITICAL: ALL field values must be written in {language_name}. Subject, greeting, intro, labels, challenges, solutions - EVERYTHING in {language_name}.
GREETING: Use the formal greeting in {language_name}. NEVER use placeholders.
Add to closing: "Note: All meetings and communications will be conducted in English."
{STRUCTURED_OUTPUT_RULES}"""


def build_html_email(data, lang_code):
    """Build dual-platform HTML email from structured data."""
    greeting = data.get("greeting", "")
    intro = data.get("intro", "")
    ataol_intro = data.get("ataol_intro", "")
    assessment_title = data.get("assessment_title", "")
    industry_label = data.get("industry_label", "Industry")
    industry_value = data.get("industry_value", "")
    stage_label = data.get("stage_label", "Stage")
    stage_value = data.get("stage_value", "")
    employee_label = data.get("employee_label", "Scale")
    employee_value = data.get("employee_value", "")
    strategic_challenges_label = data.get("strategic_challenges_label", "Strategic Challenges")
    strategic_challenges = data.get("strategic_challenges", [])
    operational_challenges_label = data.get("operational_challenges_label", "Operational Challenges")
    operational_challenges = data.get("operational_challenges", [])
    st_value_prop = data.get("st_value_prop", "")
    st_solutions = data.get("st_solutions", [])
    al_value_prop = data.get("al_value_prop", "")
    al_solutions = data.get("al_solutions", [])
    innovation_highlights = data.get("innovation_highlights", [])
    closing = data.get("closing", "")
    cta_text = data.get("cta_text", "Schedule a Call")
    company_name = data.get("_company_name", "")

    # Meeting time slots
    from datetime import datetime, timedelta
    from urllib.parse import quote
    now = datetime.utcnow()
    slots = []
    day = now + timedelta(days=2)
    while len(slots) < 3:
        if day.weekday() < 5:
            slots.append(day)
        day += timedelta(days=1)

    SLOT_LABELS = {
        "tr": {"instruction": "Size uygun olan zamani secin:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Baska bir zaman onerin"},
        "en": {"instruction": "Select a time that works for you:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Suggest another time"},
        "de": {"instruction": "Wahlen Sie eine passende Zeit:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Anderen Termin vorschlagen"},
        "fr": {"instruction": "Choisissez un creneau qui vous convient :", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Proposer un autre horaire"},
        "pt": {"instruction": "Selecione um horario conveniente:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Sugerir outro horario"},
        "ja": {"instruction": "ご都合の良い日時をお選びください:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "別の日時を提案する"},
        "es": {"instruction": "Seleccione un horario conveniente:", "morning": "10:00 - 10:30", "afternoon": "14:00 - 14:30", "other": "Sugerir otro horario"},
    }
    sl = SLOT_LABELS.get(lang_code, SLOT_LABELS["en"])
    slot_instruction = sl["instruction"]

    day_names_tr = ["Pzt", "Sal", "Car", "Per", "Cum", "Cmt", "Paz"]
    day_names_en = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    month_names_tr = ["", "Oca", "Sub", "Mar", "Nis", "May", "Haz", "Tem", "Agu", "Eyl", "Eki", "Kas", "Ara"]

    def format_slot_label(dt, time_str):
        if lang_code == "tr":
            return f"{day_names_tr[dt.weekday()]} {dt.day} {month_names_tr[dt.month]} - {time_str}"
        return f"{day_names_en[dt.weekday()]} {dt.strftime('%b %d')} - {time_str}"

    slot_labels = [
        format_slot_label(slots[0], sl["morning"]),
        format_slot_label(slots[1], sl["afternoon"]),
        sl["other"],
    ]

    mailto_subject = quote(f"Meeting Request - ATAOL AI Techs x {company_name}")
    mailto_body_1 = quote(f"Hello,\n\nI would like to schedule a meeting.\n\nPreferred time: {slot_labels[0]}\n\nBest regards")
    mailto_body_2 = quote(f"Hello,\n\nI would like to schedule a meeting.\n\nPreferred time: {slot_labels[1]}\n\nBest regards")
    mailto_body_3 = quote(f"Hello,\n\nI would like to schedule a meeting.\n\nPreferred time: \n\nBest regards")

    # Promo text
    promo_tr = "3 aylik lisans alanlara +1 ay ucretsiz kullanim | Yillik lisans alanlara %15 indirim"
    promo_en = "3-month license: +1 month free | Annual license: 15% discount"
    promo_text = promo_tr if lang_code == "tr" else promo_en

    html = f"""
<div style="max-width:620px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#2d2d2d;line-height:1.6;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0a0a1a 0%,#1a1a3e 50%,#0f2460 100%);padding:24px 30px 20px;border-radius:12px 12px 0 0;">
    <img src="{LOGO_URL}" alt="ATAOL AI Techs" style="height:48px;" />
    <div style="margin-top:12px;height:3px;background:linear-gradient(90deg,#4fc3f7,#22d3ee,#1976d2,transparent);border-radius:2px;"></div>
  </div>

  <!-- Body -->
  <div style="background:#ffffff;padding:30px;border-left:1px solid #e8e8e8;border-right:1px solid #e8e8e8;">

    <!-- Greeting + Intro -->
    <p style="margin:0 0 16px;font-size:15px;color:#1a1a2e;">{greeting}</p>
    <p style="margin:0 0 14px;font-size:14px;color:#444;">{intro}</p>
    <p style="margin:0 0 20px;font-size:14px;color:#555;font-style:italic;">{ataol_intro}</p>

    <!-- Assessment Section -->
    <div style="background:linear-gradient(135deg,#f8f9fc 0%,#eef1f7 100%);border-radius:10px;padding:22px 24px;margin:20px 0;border:1px solid #e2e6ed;">
      <table style="width:100%;margin:0 0 16px;" cellpadding="0" cellspacing="0">
        <tr>
          <td><p style="margin:0;font-size:15px;font-weight:700;color:#1a1a2e;">{assessment_title}</p></td>
          <td style="text-align:right;"><span style="background:#1a1a2e;color:#4fc3f7;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:600;letter-spacing:1px;">CONFIDENTIAL</span></td>
        </tr>
      </table>

      <!-- Info Table -->
      <table style="width:100%;border-collapse:collapse;margin:0 0 16px;" cellpadding="0" cellspacing="0">
        <tr>
          <td style="padding:8px 12px;background:#e3f2fd;border-radius:6px 0 0 6px;font-size:12px;font-weight:600;color:#1565c0;width:30%;">{industry_label}</td>
          <td style="padding:8px 12px;background:#f5f7fa;border-radius:0 6px 6px 0;font-size:12px;color:#333;">{industry_value}</td>
        </tr>
        <tr><td colspan="2" style="height:4px;"></td></tr>
        <tr>
          <td style="padding:8px 12px;background:#e8f5e9;border-radius:6px 0 0 6px;font-size:12px;font-weight:600;color:#2e7d32;width:30%;">{stage_label}</td>
          <td style="padding:8px 12px;background:#f5f7fa;border-radius:0 6px 6px 0;font-size:12px;color:#333;">{stage_value}</td>
        </tr>
        <tr><td colspan="2" style="height:4px;"></td></tr>
        <tr>
          <td style="padding:8px 12px;background:#fff3e0;border-radius:6px 0 0 6px;font-size:12px;font-weight:600;color:#e65100;width:30%;">{employee_label}</td>
          <td style="padding:8px 12px;background:#f5f7fa;border-radius:0 6px 6px 0;font-size:12px;color:#333;">{employee_value}</td>
        </tr>
      </table>

      <!-- Strategic Challenges -->
      <div style="border-left:3px solid #ef5350;padding-left:14px;margin:16px 0;">
        <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#c62828;">{strategic_challenges_label}</p>
        {"".join(f'<p style="margin:0 0 6px;font-size:13px;color:#555;padding-left:8px;">&#9656; {c}</p>' for c in strategic_challenges)}
      </div>

      <!-- Operational Challenges -->
      <div style="border-left:3px solid #ff9800;padding-left:14px;margin:16px 0 4px;">
        <p style="margin:0 0 8px;font-size:13px;font-weight:600;color:#e65100;">{operational_challenges_label}</p>
        {"".join(f'<p style="margin:0 0 6px;font-size:13px;color:#555;padding-left:8px;">&#9656; {c}</p>' for c in operational_challenges)}
      </div>
    </div>

    <!-- Platform 1: StrategyThrust -->
    <div style="background:#f8f9fc;border-radius:10px;padding:20px 24px;margin:20px 0;border-left:4px solid #1976d2;">
      <p style="margin:0 0 8px;font-size:14px;font-weight:700;color:#1a1a2e;">&#9670; Strategy<span style="color:#1976d2;">Thrust</span></p>
      <p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;">{"Stratejik Karar Destek Platformu" if lang_code == "tr" else "Strategic Decision Support Platform"}</p>
      <p style="margin:8px 0 12px;font-size:13px;color:#444;">{st_value_prop}</p>
      {"".join(f'<p style="margin:0 0 6px;font-size:13px;color:#555;padding-left:8px;">&#10004; {s}</p>' for s in st_solutions)}
    </div>

    <!-- Platform 2: ActLedger -->
    <div style="background:#f0fdf4;border-radius:10px;padding:20px 24px;margin:20px 0;border-left:4px solid #22d3ee;">
      <p style="margin:0 0 8px;font-size:14px;font-weight:700;color:#1a1a2e;">&#9670; Act<span style="color:#22d3ee;">Ledger</span></p>
      <p style="margin:0 0 4px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;">{"Operasyonel Mukemmellik Sistem Platformu" if lang_code == "tr" else "Operational Excellence System Platform"}</p>
      <p style="margin:8px 0 12px;font-size:13px;color:#444;">{al_value_prop}</p>
      {"".join(f'<p style="margin:0 0 6px;font-size:13px;color:#555;padding-left:8px;">&#10004; {s}</p>' for s in al_solutions)}
      <!-- Promo -->
      <div style="margin:14px 0 0;padding:10px 14px;background:linear-gradient(135deg,#e0f7fa,#e8f5e9);border-radius:6px;border:1px dashed #22d3ee;">
        <p style="margin:0;font-size:12px;font-weight:600;color:#0e7490;">&#127381; {promo_text}</p>
      </div>
    </div>

    <!-- Innovation Highlights -->
    <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:10px;padding:20px 24px;margin:20px 0;">
      <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#4fc3f7;text-transform:uppercase;letter-spacing:1px;">{"Inovasyon ve Dunya Ilkleri" if lang_code == "tr" else "Innovation Highlights"}</p>
      {"".join(f'<p style="margin:0 0 8px;font-size:13px;color:#e0e0e0;padding-left:8px;">&#9733; {h}</p>' for h in innovation_highlights)}
    </div>

    <!-- Services Note -->
    <p style="margin:16px 0 8px;font-size:13px;color:#555;">{data.get("services_note", "")}</p>
    <p style="margin:0 0 20px;font-size:12px;"><a href="https://www.ataolai.tech" style="color:#1976d2;text-decoration:none;font-weight:600;">www.ataolai.tech</a></p>

    <!-- Closing -->
    <p style="margin:4px 0 24px;font-size:14px;color:#444;">{closing}</p>

    <!-- Meeting Scheduler -->
    <div style="background:#f0f4ff;border-radius:10px;padding:20px 24px;margin:24px 0;border:1px solid #d0d9ed;">
      <p style="margin:0 0 12px;font-size:14px;font-weight:600;color:#1a1a2e;">{cta_text}</p>
      <p style="margin:0 0 12px;font-size:12px;color:#666;">{slot_instruction}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a href="mailto:sertacgul@strategythrust.com?subject={mailto_subject}&body={mailto_body_1}" style="display:inline-block;background:#ffffff;border:1px solid #1976d2;color:#1976d2;padding:10px 16px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;text-align:center;min-width:140px;">
          {slot_labels[0]}
        </a>
        <a href="mailto:sertacgul@strategythrust.com?subject={mailto_subject}&body={mailto_body_2}" style="display:inline-block;background:#ffffff;border:1px solid #1976d2;color:#1976d2;padding:10px 16px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;text-align:center;min-width:140px;">
          {slot_labels[1]}
        </a>
        <a href="mailto:sertacgul@strategythrust.com?subject={mailto_subject}&body={mailto_body_3}" style="display:inline-block;background:linear-gradient(135deg,#1a1a2e,#0f3460);color:#ffffff;padding:10px 16px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;text-align:center;min-width:140px;">
          {slot_labels[2]}
        </a>
      </div>
    </div>

    <p style="margin:0;font-size:13px;color:#333;">Sertac Gul<br>
    <span style="color:#888;font-size:12px;">Founder, ATAOL AI Techs</span></p>
  </div>

  <!-- Footer -->
  <div style="background:#f8f9fa;padding:20px 30px;border-radius:0 0 12px 12px;border:1px solid #e8e8e8;border-top:none;">
    <table style="width:100%;" cellpadding="0" cellspacing="0"><tr>
      <td style="vertical-align:middle;">
        <p style="margin:0 0 2px;font-size:12px;color:#666;font-weight:600;">ATAOL AI Techs</p>
        <p style="margin:0 0 2px;font-size:11px;color:#888;">{"Otomasyon, Mobil & Web Uygulama, Ozel Yazilim Cozumleri" if lang_code == "tr" else "Automation, Mobile & Web Apps, Custom Software Solutions"}</p>
        <p style="margin:0 0 2px;font-size:12px;color:#666;">+90 532 201 3416</p>
        <p style="margin:0;font-size:12px;">
          <a href="https://www.ataolai.tech" style="color:#1a1a2e;text-decoration:none;font-weight:600;">ataolai.tech</a>
          &nbsp;|&nbsp;
          <a href="https://strategythrust.com" style="color:#1976d2;text-decoration:none;">strategythrust.com</a>
          &nbsp;|&nbsp;
          <a href="https://actledger.com" style="color:#22d3ee;text-decoration:none;">actledger.com</a>
        </p>
      </td>
      <td style="vertical-align:middle;text-align:right;">
        <a href="{LINKEDIN_URL}" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px;">
          <img src="{LINKEDIN_ICON}" alt="LinkedIn" style="height:16px;width:16px;" />
          <span style="color:#0a66c2;font-size:11px;">Follow us</span>
        </a>
      </td>
    </tr></table>
    <p style="margin:12px 0 0;font-size:10px;color:#aaa;font-style:italic;">
      {"Bu e-postayi almak istemiyorsaniz, lutfen 'abonelikten cik' yazarak yanit verin." if lang_code == "tr" else "If you'd prefer not to receive these emails, simply reply with 'unsubscribe'."}
    </p>
  </div>

</div>"""
    return html


def build_text_email(data, lang_code):
    """Build plain text version of dual-platform email."""
    st_solutions_text = "\n".join(f"  - {s}" for s in data.get("st_solutions", []))
    al_solutions_text = "\n".join(f"  - {s}" for s in data.get("al_solutions", []))
    strategic_text = "\n".join(f"  - {c}" for c in data.get("strategic_challenges", []))
    operational_text = "\n".join(f"  - {c}" for c in data.get("operational_challenges", []))
    innovation_text = "\n".join(f"  * {h}" for h in data.get("innovation_highlights", []))

    promo_tr = "Kampanya: 3 aylik lisans alanlara +1 ay ucretsiz | Yillik lisans alanlara %15 indirim"
    promo_en = "Promotion: 3-month license +1 month free | Annual license 15% discount"
    promo = promo_tr if lang_code == "tr" else promo_en

    text = f"""{data.get('greeting', '')}

{data.get('intro', '')}

{data.get('ataol_intro', '')}

{data.get('assessment_title', '')}
{data.get('industry_label', 'Industry')}: {data.get('industry_value', '')}
{data.get('stage_label', 'Stage')}: {data.get('stage_value', '')}
{data.get('employee_label', 'Scale')}: {data.get('employee_value', '')}

{data.get('strategic_challenges_label', 'Strategic Challenges')}:
{strategic_text}

{data.get('operational_challenges_label', 'Operational Challenges')}:
{operational_text}

--- StrategyThrust ---
{data.get('st_value_prop', '')}
{st_solutions_text}

--- ActLedger ---
{data.get('al_value_prop', '')}
{al_solutions_text}
{promo}

{innovation_text}

{data.get('services_note', '')}
www.ataolai.tech

{data.get('closing', '')}

{data.get('cta_text', '')}
Reply to: sertacgul@strategythrust.com

--
Sertac Gul | Founder, ATAOL AI Techs
Otomasyon, Mobil & Web Uygulama, Ozel Yazilim Cozumleri
Tel: +90 532 201 3416
https://www.ataolai.tech | https://strategythrust.com | https://actledger.com
LinkedIn: {LINKEDIN_URL}

{"Bu e-postayi almak istemiyorsaniz, lutfen 'abonelikten cik' yazarak yanit verin." if lang_code == "tr" else "If you'd prefer not to receive these emails, simply reply with 'unsubscribe'."}
"""
    return text


def get_localized_footer(language):
    """No-op - footer is built into the template."""
    return "", ""


def generate_email(lead, analysis_data, language="en"):
    """Generate a personalized dual-platform outreach email using Gemini + HTML template."""
    from localization import get_language, get_language_name

    country = lead.get("country", "INT") or "INT"
    lang_code = get_language(country)
    lang_name = get_language_name(country)

    system = get_localized_system_prompt(lang_code, lang_name, country)

    try:
        pain_points = json.loads(lead["pain_points"]) if isinstance(lead["pain_points"], str) else lead["pain_points"]
    except (json.JSONDecodeError, TypeError):
        pain_points = []

    try:
        service_match = json.loads(lead["service_match"]) if isinstance(lead["service_match"], str) else lead["service_match"]
    except (json.JSONDecodeError, TypeError):
        service_match = []

    contact_name = lead.get("decision_maker", "") or ""
    contact_title = lead.get("decision_maker_title", "") or ""

    user_content = f"""Sirket: {lead['company_name']}
Website: {lead['website']}
Ulke: {country}
Hedef dil: {lang_name}
Sektor: {lead.get('industry', 'Bilinmiyor')}
Sirket asamasi: {lead.get('company_size', 'Bilinmiyor')}
Ne yapiyorlar: {lead.get('company_summary', '')}
Zorluklar: {json.dumps(pain_points, ensure_ascii=False)}
Cozumlerimiz: {json.dumps(service_match, ensure_ascii=False)}
Kisi adi: {contact_name}
Kisi unvani: {contact_title}

Yukaridaki firma analiz verilerini kullanarak, {lang_name} dilinde ATAOL AI Techs'in iki platformunu (StrategyThrust + ActLedger) tanitan yapilandirilmis JSON ciktisi olustur."""

    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=8192,
        ),
    )

    structured = parse_json_response(response.text)
    if not structured:
        return {"error": "Could not parse response", "raw": response.text}

    structured["_company_name"] = lead['company_name']

    body_html = build_html_email(structured, lang_code)
    body_text = build_text_email(structured, lang_code)

    return {
        "subject": structured.get("subject", ""),
        "body_html": body_html,
        "body_text": body_text,
        "language": lang_code,
    }


def run_email_generation(max_leads=10):
    """Generate emails for analyzed leads that don't have emails yet."""
    db = get_db()

    contacted_emails = set()
    rows = db.execute("SELECT DISTINCT to_email FROM emails WHERE email_type = 'initial'").fetchall()
    for row in rows:
        if row["to_email"]:
            contacted_emails.add(row["to_email"].lower())

    leads = db.execute(
        """SELECT l.* FROM leads l
           WHERE l.analysis_status = 'success'
             AND l.is_excluded = 0
             AND l.status NOT IN ('completed', 'contacted', 'email_generated')
             AND (l.decision_maker_email != '' OR l.emails_found != '[]')
             AND l.id NOT IN (SELECT lead_id FROM emails WHERE email_type = 'initial')
           ORDER BY l.analyzed_at ASC LIMIT ?""",
        (max_leads,),
    ).fetchall()

    if not leads:
        print("No leads ready for email generation.")
        db.close()
        return 0

    generated = 0
    for lead in leads:
        to_email = lead["decision_maker_email"]
        if not to_email:
            try:
                found = json.loads(lead["emails_found"])
                if found:
                    to_email = found[0]
            except (json.JSONDecodeError, TypeError):
                pass

        if not to_email:
            print(f"  No email for {lead['company_name']}, skipping.")
            continue

        if to_email.lower() in contacted_emails:
            print(f"  Already contacted {to_email}, skipping.")
            continue

        print(f"\nGenerating email for: {lead['company_name']} -> {to_email}")
        contacted_emails.add(to_email.lower())

        email_data = generate_email(dict(lead), None, lead["language"])

        if email_data.get("error"):
            print(f"  Failed: {email_data['error']}")
            continue

        db.execute(
            """INSERT INTO emails (lead_id, subject, body_html, body_text, language, to_email, to_name, from_email, status, model_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?)""",
            (
                lead["id"],
                email_data.get("subject", ""),
                email_data.get("body_html", ""),
                email_data.get("body_text", ""),
                email_data.get("language", "en"),
                to_email,
                lead["decision_maker"] or lead["company_name"],
                Config.GMAIL_SENDER_EMAIL,
                Config.GEMINI_MODEL,
            ),
        )
        db.execute(
            "UPDATE leads SET status = 'email_generated', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lead["id"],),
        )
        db.commit()
        log_activity(db, "email_generated", "lead", lead["id"], f"To: {to_email}")
        generated += 1
        print(f"  Subject: {email_data.get('subject', '')}")

    db.close()
    print(f"\nEmail generation complete. Generated {generated}/{len(leads)} emails.")
    return generated


if __name__ == "__main__":
    print("=== ATAOL AI Techs Email Generator ===\n")
    run_email_generation(max_leads=5)
