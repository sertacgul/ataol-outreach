"""
Multi-source contact enrichment module.

When the website scraper can't find a personal email, this module
searches LinkedIn and Crunchbase/website sources via Gemini + Google Search
to find decision maker info (name, title, LinkedIn URL, bio).

Called from scraper.py's scrape_company() when no personal email is found.
"""

import json
from urllib.parse import urlparse
from google import genai
from google.genai import types
from config import Config

gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)


def _parse_json_response(text):
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


EMPTY_LINKEDIN = {"name": "", "title": "", "linkedin_url": "", "bio": ""}
EMPTY_CRUNCHBASE = {"name": "", "title": ""}


def search_linkedin(domain, company_name, language="tr"):
    """Search LinkedIn for the company's top decision maker via Gemini + Google Search.

    Returns dict: {name, title, linkedin_url, bio}
    """
    prompt = f"""Bu sirketin ust duzey karar vericisini LinkedIn'de bul: {domain}

ARAMA: LinkedIn'de "{domain}" veya "{company_name}" sirketindeki
CEO, Founder, CTO, Managing Director, Genel Mudur, Kurucu ara.

ONCELIK: CEO/Founder > CTO/COO > Managing Director > VP > Director

SADECE gecerli JSON yanit ver (markdown yok, kod blogu yok):
{{"name": "Ad Soyad", "title": "CEO", "linkedin_url": "https://linkedin.com/in/...", "bio": "Kisa ozet - gecmis deneyim, uzmanlik alani (max 2 cumle)"}}

Bulamazsan tum alanlari bos birak:
{{"name": "", "title": "", "linkedin_url": "", "bio": ""}}"""

    try:
        from pipeline.gemini_utils import call_gemini
        response = call_gemini(
            gemini_client,
            Config.GEMINI_MODEL,
            prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        if response and response.text:
            result = _parse_json_response(response.text)
            if result and result.get("name"):
                print(f"  LinkedIn found: {result['name']} ({result.get('title', '')})")
                return {
                    "name": result.get("name", ""),
                    "title": result.get("title", ""),
                    "linkedin_url": result.get("linkedin_url", ""),
                    "bio": result.get("bio", ""),
                }
    except Exception as e:
        print(f"  LinkedIn search failed: {e}")

    return dict(EMPTY_LINKEDIN)


def search_crunchbase_website(domain, company_name, language="tr"):
    """Search Crunchbase, Bloomberg, PitchBook and company website for decision maker.

    Returns dict: {name, title}
    """
    prompt = f"""Bu sirketin karar vericisini bul: {domain}

KAYNAK 1: Crunchbase, Bloomberg, PitchBook'ta "{company_name}" kurucu/CEO
KAYNAK 2: Sirketin kendi about/team sayfasi
KAYNAK 3: Turkce firmalar icin kariyer.net, sikayetvar, startups.watch

ONCELIK: CEO/Founder > CTO/COO > Managing Director > VP > Director

SADECE gecerli JSON yanit ver (markdown yok, kod blogu yok):
{{"name": "Ad Soyad", "title": "CEO"}}

Bulamazsan tum alanlari bos birak:
{{"name": "", "title": ""}}"""

    try:
        from pipeline.gemini_utils import call_gemini
        response = call_gemini(
            gemini_client,
            Config.GEMINI_MODEL,
            prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        if response and response.text:
            result = _parse_json_response(response.text)
            if result and result.get("name"):
                print(f"  Crunchbase/web found: {result['name']} ({result.get('title', '')})")
                return {
                    "name": result.get("name", ""),
                    "title": result.get("title", ""),
                }
    except Exception as e:
        print(f"  Crunchbase/web search failed: {e}")

    return dict(EMPTY_CRUNCHBASE)


def merge_results(linkedin_result, crunchbase_result):
    """Merge results with LinkedIn taking priority.

    - LinkedIn name/title used if available, else Crunchbase
    - linkedin_url and bio only come from LinkedIn
    """
    name = linkedin_result.get("name") or crunchbase_result.get("name") or ""
    title = linkedin_result.get("title") or crunchbase_result.get("title") or ""
    linkedin_url = linkedin_result.get("linkedin_url", "")
    bio = linkedin_result.get("bio", "")

    source = ""
    if linkedin_result.get("name"):
        source = "linkedin"
    elif crunchbase_result.get("name"):
        source = "crunchbase"

    return {
        "name": name,
        "title": title,
        "linkedin_url": linkedin_url,
        "bio": bio,
        "source": source,
    }


def enrich_contact(domain, company_name, language="tr"):
    """Main entry point for multi-source contact enrichment.

    Called from scraper.py when no personal email is found after website scrape.

    1. Search LinkedIn for decision maker
    2. Search Crunchbase + company website
    3. Merge results (LinkedIn priority)

    Returns dict: {name, title, linkedin_url, bio, source}
    source is "linkedin", "crunchbase", or "" if nothing found.
    """
    print(f"  Enrichment: searching LinkedIn for {company_name} ({domain})")
    linkedin_result = search_linkedin(domain, company_name, language)

    print(f"  Enrichment: searching Crunchbase/web for {company_name} ({domain})")
    crunchbase_result = search_crunchbase_website(domain, company_name, language)

    merged = merge_results(linkedin_result, crunchbase_result)

    if merged["name"]:
        print(f"  Enrichment result: {merged['name']} ({merged['title']}) via {merged['source']}")
    else:
        print(f"  Enrichment: no decision maker found for {company_name}")

    return merged
