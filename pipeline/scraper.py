import re
import time
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from database import get_db, log_activity
from config import Config

gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Pages to try scraping for contact info (kept short for speed)
CONTACT_PATHS_EN = ["/contact", "/about"]
CONTACT_PATHS_TR = ["/iletisim", "/hakkimizda"]


def check_robots_txt(base_url):
    """Check if scraping is allowed by robots.txt."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/robots.txt", timeout=5, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.text.lower()
            # Simple check: if "disallow: /" for all user agents, skip
            if "user-agent: *" in content and "disallow: /" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "user-agent: *" in line:
                        for j in range(i + 1, min(i + 5, len(lines))):
                            if lines[j].strip() == "disallow: /":
                                return False
        return True
    except Exception:
        return True  # if we can't check, proceed cautiously


def fetch_page(url, timeout=10):
    """Fetch a page and return BeautifulSoup + raw text."""
    try:
        resp = requests.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove noise
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return soup, text[:5000], resp.text
        return None, "", ""
    except Exception:
        return None, "", ""


def extract_emails_from_html(raw_html):
    """Find all email addresses in raw HTML."""
    emails = set(re.findall(EMAIL_REGEX, raw_html))
    # Filter out image/file extensions mistakenly caught
    filtered = set()
    for email in emails:
        ext = email.split(".")[-1].lower()
        if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js"):
            filtered.add(email.lower())
    return filtered


def prioritize_emails(emails):
    """Sort emails: decision-maker > named > generic."""
    priority_prefixes = ["ceo", "founder", "cto", "coo", "director", "manager", "kurucu", "genel", "baskan"]
    depriority_prefixes = ["info@", "contact@", "hello@", "support@", "noreply@", "iletisim@", "destek@", "sales@"]

    scored = []
    for email in emails:
        local = email.split("@")[0].lower()
        if any(p in local for p in priority_prefixes):
            scored.append((0, email))
        elif any(email.lower().startswith(d) for d in depriority_prefixes):
            scored.append((2, email))
        else:
            scored.append((1, email))

    scored.sort(key=lambda x: x[0])
    return [e for _, e in scored]


def extract_decision_maker(soup, text):
    """Try to find decision maker name and title from the page."""
    # Look for common patterns in team/about pages
    title_keywords = [
        "CEO", "CTO", "COO", "CFO", "Founder", "Co-Founder",
        "Kurucu", "Genel Mudir", "Baskan", "Yonetim Kurulu",
        "Managing Director", "President", "Owner",
    ]

    name = ""
    title = ""

    # Try meta tags or structured data
    if soup:
        # Look for structured person data
        for heading in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
            heading_text = heading.get_text(strip=True)
            for kw in title_keywords:
                if kw.lower() in heading_text.lower():
                    title = kw
                    # Name might be nearby
                    prev = heading.find_previous(["h2", "h3", "h4", "strong", "p"])
                    nxt = heading.find_next(["h2", "h3", "h4", "strong", "p"])
                    if prev and len(prev.get_text(strip=True)) < 50:
                        name = prev.get_text(strip=True)
                    elif nxt and len(nxt.get_text(strip=True)) < 50:
                        name = nxt.get_text(strip=True)
                    if name and title:
                        return name, title

    return name, title


def scrape_company(website_url, language="tr"):
    """Scrape a company website for contact info and page content."""
    base_url = website_url.rstrip("/")

    # Check robots.txt
    if not check_robots_txt(base_url):
        return {"error": "robots.txt disallows scraping", "page_text": "", "emails_found": [], "best_email": ""}

    contact_paths = CONTACT_PATHS_TR + CONTACT_PATHS_EN
    pages_to_try = [base_url] + [f"{base_url}{path}" for path in contact_paths]

    all_text = ""
    all_emails = set()
    decision_maker_name = ""
    decision_maker_title = ""

    for page_url in pages_to_try:
        soup, text, raw_html = fetch_page(page_url)
        if not soup:
            continue

        all_text += f"\n--- {page_url} ---\n{text}"
        emails = extract_emails_from_html(raw_html)
        all_emails.update(emails)

        # Try to find decision maker
        if not decision_maker_name:
            name, title = extract_decision_maker(soup, text)
            if name:
                decision_maker_name = name
                decision_maker_title = title

        time.sleep(1)  # polite but fast

    # Validate all found emails (KEP filter, format, MX, patterns)
    from pipeline.email_validator import validate_and_filter_emails, pick_best_email
    valid_emails, rejected = validate_and_filter_emails(list(all_emails))
    for email, reason in rejected:
        print(f"    Rejected: {email} ({reason})")

    # If no valid email found via scraping, ask Gemini
    if not valid_emails:
        gemini_result = find_contact_with_gemini(base_url, language)
        if gemini_result.get("email"):
            from pipeline.email_validator import validate_email
            is_valid, reason = validate_email(gemini_result["email"])
            if is_valid:
                valid_emails.append(gemini_result["email"])
            else:
                print(f"    Gemini email rejected: {gemini_result['email']} ({reason})")
        if gemini_result.get("decision_maker") and not decision_maker_name:
            decision_maker_name = gemini_result["decision_maker"]
            decision_maker_title = gemini_result.get("decision_maker_title", "")

    best_email = pick_best_email(valid_emails) if valid_emails else ""

    return {
        "page_text": all_text[:10000],
        "emails_found": valid_emails,
        "best_email": best_email,
        "decision_maker": decision_maker_name,
        "decision_maker_title": decision_maker_title,
    }


def find_contact_with_gemini(website_url, language="tr"):
    """Use Gemini with Google Search to find contact email and decision maker."""
    try:
        prompt = f"""Bu sirketin iletisim e-posta adresini ve karar vericisini (CEO/Founder/Genel Mudur) bul:
{website_url}

SADECE gecerli JSON yanit ver (markdown yok, kod blogu yok):
{{"email": "iletisim@sirket.com", "decision_maker": "Ad Soyad", "decision_maker_title": "CEO"}}

Bulamazsan bos string ver: {{"email": "", "decision_maker": "", "decision_maker_title": ""}}"""

        response = gemini_client.models.generate_content(
            model=Config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )

        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            if result.get("email"):
                print(f"  Gemini found: {result['email']} ({result.get('decision_maker', '')})")
            return result
    except Exception as e:
        print(f"  Gemini contact search failed: {e}")

    return {"email": "", "decision_maker": "", "decision_maker_title": ""}


def run_scraping(max_leads=10):
    """Scrape unscraped leads."""
    db = get_db()
    leads = db.execute(
        "SELECT * FROM leads WHERE scrape_status = 'pending' AND is_excluded = 0 ORDER BY discovered_at ASC LIMIT ?",
        (max_leads,),
    ).fetchall()

    if not leads:
        print("No leads to scrape.")
        db.close()
        return 0

    scraped = 0
    for lead in leads:
        print(f"\nScraping: {lead['company_name']} ({lead['website']})")
        result = scrape_company(lead["website"], lead["language"])

        if result.get("error"):
            print(f"  Skipped: {result['error']}")
            db.execute(
                "UPDATE leads SET scrape_status = 'skipped', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (lead["id"],),
            )
        else:
            emails_json = json.dumps(result["emails_found"])
            db.execute(
                """UPDATE leads SET
                    emails_found = ?,
                    decision_maker = ?,
                    decision_maker_title = ?,
                    decision_maker_email = ?,
                    scrape_status = 'success',
                    status = 'scraped',
                    scraped_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    emails_json,
                    result["decision_maker"],
                    result["decision_maker_title"],
                    result["best_email"],
                    lead["id"],
                ),
            )
            # Store page text temporarily for analysis (in analysis_raw for now)
            db.execute(
                "UPDATE leads SET analysis_raw = ? WHERE id = ?",
                (result["page_text"], lead["id"]),
            )
            scraped += 1
            print(f"  Emails found: {result['emails_found']}")
            print(f"  Best email: {result['best_email']}")

        db.commit()
        log_activity(db, "lead_scraped", "lead", lead["id"], f"Emails: {len(result.get('emails_found', []))}")

    db.close()
    print(f"\nScraping complete. Scraped {scraped}/{len(leads)} leads.")
    return scraped


if __name__ == "__main__":
    print("=== ATAOL AI Techs Web Scraper ===\n")
    run_scraping(max_leads=5)
