import json
from google import genai
from google.genai import types
from database import get_db, log_activity
from config import Config

client = genai.Client(api_key=Config.GEMINI_API_KEY)


ATAOL_CONTEXT = """ATAOL AI Techs, iki ayrı platform sunan bir teknoloji sirketidir:

1. StrategyThrust - Stratejik Karar Destek Platformu:
- Geleneksel danismanlik 3-6 ay surer. StrategyThrust ayni kalitedeki ciktiyi 72 saat icinde tamamlar.
- Geleneksel yonetim danismanliginin yaklasik 150'de 1 fiyatina ayni kalitede cikti.
- Sektor analizi, rekabet konumlandirmasi, pazar dinamikleri ve stratejik projeksiyonlar.

2. ActLedger - Performans ve Operasyon Yonetim Platformu:
- 15 sektor, 576+ departman, 7800+ hazir KPI ile dunyanin en kapsamli sektor-spesifik KPI kutuphanesi.
- 5 katmanli performans olcum cercevesi (Performance, Quality, Time, Risk, AI Insight).
- Sektor secimi ile dakikalar icinde tam operasyonel cerceve kurulumu - kurumsal cozumlerin aksine aylar degil.
- Saha operasyonlari, envanter takibi, is akislari, otomasyon, IoT entegrasyonu.
- OperIQ: Saha raporlarinin otomatik analizi.
- Mobil-first: iOS native app + PWA.
- 50+ ulke dil ve timezone destegi.

Website: strategythrust.com | actledger.com
Kurucu: Sertac Gul"""


SYSTEM_PROMPT_TR = f"""ATAOL AI Techs icin stratejik analist olarak calisiyorsun. Gorevir sirketleri analiz edip ATAOL'un iki platformunun (StrategyThrust ve ActLedger) onlara nasil yardimci olabilecegini belirlemek.

ATAOL AI Techs Hakkinda:
{ATAOL_CONTEXT}

Verilen sirket bilgilerini analiz et. Hem stratejik hem operasyonel zorluklarini belirle.

SADECE gecerli JSON formatinda yanit ver (markdown yok, kod blogu yok):
{{
  "company_summary": "Sirketin ne yaptigina dair 2-3 cumlelik aciklama",
  "industry": "Sektor",
  "company_stage": "startup | growth-stage | mid-size | enterprise",
  "employee_count_estimate": "10-50 | 50-200 | 200-1000 | 1000+",
  "strategic_pain_points": ["2-3 spesifik STRATEJIK zorluk - karar alma hizi, pazar konumlandirmasi, rekabet baskisi, buyume darbogazlari"],
  "operational_pain_points": ["2-3 spesifik OPERASYONEL zorluk - performans takibi, KPI eksikligi, saha yonetimi, verimlilik, raporlama"],
  "strategythrust_match": ["StrategyThrust'in bu sirkete nasil yardimci olacagi - somut ol"],
  "actledger_match": ["ActLedger'in bu sirkete nasil yardimci olacagi - somut ol"],
  "primary_platform": "strategythrust | actledger | both",
  "outreach_angle": "Ulasim icin en guclu neden - ONLARIN spesifik sorununu ATAOL'un cozumlerine bagla",
  "tone_suggestion": "formal | professional-casual | startup-friendly"
}}"""

SYSTEM_PROMPT_EN = f"""You are a strategic analyst for ATAOL AI Techs. Your job is to analyze companies and identify how ATAOL's two platforms (StrategyThrust and ActLedger) can help them.

About ATAOL AI Techs:
{ATAOL_CONTEXT}

Analyze the company information provided. Identify both their strategic AND operational challenges.

Respond ONLY in valid JSON format (no markdown, no code blocks):
{{
  "company_summary": "2-3 sentence description of what this company does",
  "industry": "their industry sector",
  "company_stage": "startup | growth-stage | mid-size | enterprise",
  "employee_count_estimate": "10-50 | 50-200 | 200-1000 | 1000+",
  "strategic_pain_points": ["2-3 specific STRATEGIC challenges - decision-making speed, market positioning, competitive pressure, growth bottlenecks"],
  "operational_pain_points": ["2-3 specific OPERATIONAL challenges - performance tracking, KPI gaps, field management, efficiency, reporting"],
  "strategythrust_match": ["specific ways StrategyThrust can help THIS company - be concrete"],
  "actledger_match": ["specific ways ActLedger can help THIS company - be concrete"],
  "primary_platform": "strategythrust | actledger | both",
  "outreach_angle": "the single strongest reason to reach out - connect THEIR specific challenge to ATAOL's solutions",
  "tone_suggestion": "formal | professional-casual | startup-friendly"
}}"""


def parse_json_response(text):
    """Parse JSON from Gemini response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return None


def analyze_company(company_name, website, page_text, language="en"):
    """Analyze a company using Gemini API for dual-platform fit."""
    system = SYSTEM_PROMPT_TR if language == "tr" else SYSTEM_PROMPT_EN
    prompt = f"Sirket: {company_name}\nWebsite: {website}\n\nWeb sitesi icerigi:\n{page_text[:8000]}"

    response = client.models.generate_content(
        model=Config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=8192,
        ),
    )

    response_text = response.text
    analysis = parse_json_response(response_text)
    if not analysis:
        return {"error": "Could not parse Gemini response", "raw": response_text}

    # Merge pain points for backward compatibility with existing DB schema
    all_pain_points = analysis.get("strategic_pain_points", []) + analysis.get("operational_pain_points", [])
    all_service_match = analysis.get("strategythrust_match", []) + analysis.get("actledger_match", [])
    analysis["pain_points"] = all_pain_points
    analysis["service_match"] = all_service_match
    analysis["raw_response"] = response_text
    return analysis


def run_analysis(max_leads=10):
    """Analyze scraped leads that haven't been analyzed yet."""
    db = get_db()
    leads = db.execute(
        """SELECT * FROM leads
           WHERE scrape_status = 'success'
             AND analysis_status = 'pending'
             AND is_excluded = 0
             AND (decision_maker_email != '' OR emails_found != '[]')
           ORDER BY scraped_at ASC LIMIT ?""",
        (max_leads,),
    ).fetchall()

    if not leads:
        print("No leads to analyze.")
        db.close()
        return 0

    analyzed = 0
    for lead in leads:
        print(f"\nAnalyzing: {lead['company_name']} ({lead['website']})")

        page_text = lead["analysis_raw"]
        if not page_text:
            print("  No page text available, skipping.")
            db.execute(
                "UPDATE leads SET analysis_status = 'skipped', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (lead["id"],),
            )
            db.commit()
            continue

        analysis = analyze_company(
            lead["company_name"],
            lead["website"],
            page_text,
            lead["language"],
        )

        if analysis.get("error"):
            print(f"  Analysis failed: {analysis['error']}")
            db.execute(
                "UPDATE leads SET analysis_status = 'failed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (lead["id"],),
            )
        else:
            db.execute(
                """UPDATE leads SET
                    company_summary = ?,
                    industry = COALESCE(NULLIF(?, ''), industry),
                    company_size = COALESCE(NULLIF(?, ''), company_size),
                    pain_points = ?,
                    service_match = ?,
                    analysis_raw = ?,
                    analysis_status = 'success',
                    status = 'analyzed',
                    analyzed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    analysis.get("company_summary", ""),
                    analysis.get("industry", ""),
                    analysis.get("company_stage", ""),
                    json.dumps(analysis.get("pain_points", []), ensure_ascii=False),
                    json.dumps(analysis.get("service_match", []), ensure_ascii=False),
                    analysis.get("raw_response", ""),
                    lead["id"],
                ),
            )
            analyzed += 1
            print(f"  Industry: {analysis.get('industry', 'N/A')}")
            print(f"  Stage: {analysis.get('company_stage', 'N/A')}")
            print(f"  Primary platform: {analysis.get('primary_platform', 'N/A')}")
            print(f"  Outreach angle: {analysis.get('outreach_angle', 'N/A')}")

        db.commit()
        log_activity(db, "lead_analyzed", "lead", lead["id"])

    db.close()
    print(f"\nAnalysis complete. Analyzed {analyzed}/{len(leads)} leads.")
    return analyzed


if __name__ == "__main__":
    print("=== ATAOL AI Techs Company Analyzer ===\n")
    run_analysis(max_leads=5)
