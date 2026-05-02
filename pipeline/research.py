import time
import json
from urllib.parse import urlparse
from google import genai
from google.genai import types
from database import get_db, log_activity
from config import Config

client = genai.Client(api_key=Config.GEMINI_API_KEY)


SEARCH_QUERIES_TR = [
    "Turkiye'de performans yonetimi ve KPI takibi arayan orta olcekli sirketler",
    "Istanbul'da dijital donusum ve operasyonel verimlilik arayan firmalar",
    "Turkiye'de saha operasyonu yoneten uretim ve imalat sirketleri",
    "Hizli buyuyen Turk startuplari strateji danismanligi arayan",
    "Turkiye'de ERP ve SAP alternatifi arayan sirketler 2025 2026",
    "Turkiye'de lojistik ve tedarik zinciri sirketleri teknoloji ihtiyaci",
    "Istanbul merkezli SaaS ve fintech startuplari web siteleri",
    "Turkiye'de insaat ve gayrimenkul teknoloji sirketleri",
    "Turkiye'de saglik ve hastane yonetimi teknoloji ihtiyaci",
    "Turkiye'de enerji sektoru dijital donusum sirketleri",
    "Turkiye'de perakende ve e-ticaret buyuyen sirketler",
    "Turkiye'de gida uretimi ve FMCG sirketleri operasyonel verimlilik",
    "Turkiye'de otelcilik ve restoran zinciri buyuyen isletmeler",
    "Turkiye'de belediye ve kamu yonetimi dijital donusum",
    "Turkiye'de medya ve yayin sektoru buyuyen sirketler",
    "Turkiye'de sigorta teknolojisi ve finansal hizmetler startuplari",
    "Ankara Izmir Bursa'da buyuyen orta olcekli uretim sirketleri",
    "Turkiye'de siber guvenlik ve IT hizmetleri sirketleri",
    "Turkiye'de ulasim ve mobilite startuplari web siteleri",
    "Turkiye'de insan kaynaklari ve HR teknoloji sirketleri",
]

SEARCH_QUERIES_EN = [
    "European mid-market companies seeking KPI management and performance tracking solutions",
    "Growth stage companies needing strategic consulting and operational efficiency",
    "Manufacturing companies digital transformation Europe 2025 2026",
    "Companies looking for SAP alternatives performance management affordable",
    "UK Germany SaaS startups seeking consulting and growth strategy",
    "Fast growing European startups with websites series A B funded",
    "UAE Dubai companies needing operational management solutions",
    "Nordic tech startups growing fast strategy consulting needs",
    "Southeast Asia Singapore companies performance management needs",
    "US fastest growing startups seeking strategic analysis 2025 2026",
    "European healthcare companies operational efficiency technology",
    "Latin America tech companies growing fast needing management tools",
    "Middle East construction logistics companies digital transformation",
    "African tech startups growing fast 2025 2026 with websites",
    "European retail companies operational performance management needs",
]

RESEARCH_PROMPT_TR = """Asagidaki arama sorgusuna gore gercek sirketleri bul. Her sirket icin web sitesini, ulkesini ve kisa aciklamasini ver.

Kurallar:
- SADECE gercek, aktif sirketlerin bilgilerini ver
- Haber siteleri, blog'lar, dizin siteleri, devlet kuruluslari VERME
- Her sirketin web sitesi gercek ve erisebilir olmali
- Startup, orta olcekli veya buyumeye acik sirketlere odaklan
- Minimum 5, maksimum 10 sirket bul

SADECE gecerli JSON formatinda yanit ver (markdown yok, kod blogu yok):
{
  "companies": [
    {
      "company_name": "Sirket Adi",
      "website": "https://example.com",
      "country": "TR",
      "description": "Kisa aciklama"
    }
  ]
}

ONEMLI: country alani ISO 2 harfli ulke kodu olmali (TR, US, DE, FR, GB, AE, SG, BR vb.)"""

RESEARCH_PROMPT_EN = """Find real companies based on the search query below. For each company provide their website, country code, and brief description.

Rules:
- ONLY provide info about real, active companies
- Do NOT include news sites, blogs, directories, government agencies
- Each company's website must be real and accessible
- Focus on startups, mid-size, or growth-stage companies
- Minimum 5, maximum 10 companies

Respond ONLY in valid JSON (no markdown, no code blocks):
{
  "companies": [
    {
      "company_name": "Company Name",
      "website": "https://example.com",
      "country": "US",
      "description": "Brief description"
    }
  ]
}

IMPORTANT: country field MUST be ISO 2-letter country code (US, GB, DE, FR, AE, SG, BR, etc.)"""


def normalize_domain(url):
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        domain = parsed.netloc or parsed.path.split("/")[0]
        domain = domain.lower().replace("www.", "")
        return domain
    except Exception:
        return url.lower()


def get_existing_domains(db):
    rows = db.execute("SELECT website FROM leads").fetchall()
    return {normalize_domain(row["website"]) for row in rows}


def get_existing_emails(db):
    rows = db.execute("SELECT DISTINCT to_email FROM emails").fetchall()
    return {row["to_email"].lower() for row in rows if row["to_email"]}


def parse_json_response(text):
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


def search_leads_with_gemini(query, language="tr", exclude_names=None):
    system = RESEARCH_PROMPT_TR if language == "tr" else RESEARCH_PROMPT_EN

    exclude_text = ""
    if exclude_names:
        exclude_text = f"\n\nDaha once iletisim kurulmus firmalar - bunlari ONERME:\n{', '.join(exclude_names[:50])}"

    try:
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=f"Arama sorgusu: {query}{exclude_text}",
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=8192,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        result = parse_json_response(response.text)
        if result and "companies" in result:
            return result["companies"]
        return []
    except Exception as e:
        print(f"  Gemini search error: {e}")
        return []


SKIP_DOMAINS = [
    "wikipedia.org", "linkedin.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "medium.com", "github.com",
    "crunchbase.com", "bloomberg.com", "reuters.com", "forbes.com",
    "techcrunch.com", "google.com", "amazon.com", "apple.com",
    "microsoft.com", "hurriyet.com.tr", "milliyet.com.tr",
    "sabah.com.tr", "haberturk.com", "ntv.com.tr", "bbc.com",
    "webrazzi.com", "startups.watch", "gov.tr",
    "strategythrust.com", "actledger.com",
]


def run_research(max_queries=3, region="tr-tr", language="tr"):
    db = get_db()
    existing_domains = get_existing_domains(db)

    recent_leads = db.execute("SELECT company_name FROM leads ORDER BY id DESC LIMIT 200").fetchall()
    exclude_names = [r["company_name"] for r in recent_leads]
    queries = SEARCH_QUERIES_TR if language == "tr" else SEARCH_QUERIES_EN

    executed = db.execute("SELECT query_text FROM search_queries").fetchall()
    executed_texts = {row["query_text"] for row in executed}
    remaining = [q for q in queries if q not in executed_texts]

    if not remaining:
        print("All search queries have been executed. Re-running from start.")
        remaining = queries

    queries_to_run = remaining[:max_queries]
    total_new = 0

    for query in queries_to_run:
        print(f"\nSearching with Gemini: {query}")
        companies = search_leads_with_gemini(query, language, exclude_names[:50])

        new_count = 0
        for company in companies:
            website = company.get("website", "")
            if not website:
                continue

            domain = normalize_domain(website)

            if any(skip in domain for skip in SKIP_DOMAINS):
                continue

            if domain in existing_domains:
                continue

            company_name = company.get("company_name", domain)
            country = company.get("country", "TR" if language == "tr" else "INT")

            try:
                db.execute(
                    """INSERT INTO leads (company_name, website, country, language, source, search_query, status)
                       VALUES (?, ?, ?, ?, 'gemini', ?, 'discovered')""",
                    (company_name, website, country, language, query),
                )
                existing_domains.add(domain)
                new_count += 1
                print(f"  + {company_name} ({website})")
            except Exception:
                continue

        db.execute(
            "INSERT INTO search_queries (query_text, region, results_count) VALUES (?, ?, ?)",
            (query, region, new_count),
        )
        db.commit()

        log_activity(db, "research_search", "search", details=f"Query: {query}, Found: {new_count} new leads")
        print(f"  Found {new_count} new leads")
        total_new += new_count

        time.sleep(2)

    db.close()
    print(f"\nResearch complete. Total new leads: {total_new}")
    return total_new


if __name__ == "__main__":
    print("=== ATAOL AI Techs Lead Research ===\n")
    print("Searching Turkish companies...")
    run_research(max_queries=2, region="tr-tr", language="tr")
    print("\nSearching international companies...")
    run_research(max_queries=1, region="wt-wt", language="en")
