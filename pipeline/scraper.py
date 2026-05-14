import re
import sys
import time
import json
import requests
from urllib.parse import urljoin, urlparse

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from bs4 import BeautifulSoup
from database import get_db, log_activity

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


def has_personal_email(emails):
    """Check if any email in the list is a personal (non-generic) address."""
    generic_prefixes = ["info@", "contact@", "hello@", "hi@", "iletisim@", "bilgi@",
                        "sales@", "satis@", "marketing@", "support@", "destek@"]
    for email in emails:
        if not any(email.lower().startswith(p) for p in generic_prefixes):
            return True
    return False


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
    decision_maker_linkedin = ""
    decision_maker_bio = ""

    for page_url in pages_to_try:
        soup, text, raw_html = fetch_page(page_url)
        if not soup:
            continue

        all_text += f"\n--- {page_url} ---\n{text}"
        emails = extract_emails_from_html(raw_html)
        all_emails.update(emails)

        # Try to find decision maker from HTML
        if not decision_maker_name:
            name, title = extract_decision_maker(soup, text)
            if name:
                decision_maker_name = name
                decision_maker_title = title

        time.sleep(1)

    # Validate all found emails
    from pipeline.email_validator import validate_and_filter_emails, pick_best_email
    valid_emails, rejected = validate_and_filter_emails(list(all_emails))
    for email, reason in rejected:
        print(f"    Rejected: {email} ({reason})")

    # If we have a personal email from website scrape, skip enrichment
    needs_enrichment = not has_personal_email(valid_emails)

    if needs_enrichment:
        # Multi-source enrichment: LinkedIn + Crunchbase/website
        from pipeline.contact_enrichment import enrich_contact
        domain = urlparse(website_url).netloc.replace("www.", "")
        company_name = domain.split(".")[0].title()
        enrichment = enrich_contact(domain, company_name, language)

        if enrichment["name"]:
            decision_maker_name = enrichment["name"]
            decision_maker_title = enrichment["title"]
            decision_maker_linkedin = enrichment["linkedin_url"]
            decision_maker_bio = enrichment["bio"]
    else:
        print(f"  Personal email found in website scrape, skipping enrichment")

    # Try email pattern guessing if we have a decision maker name
    if decision_maker_name:
        pattern_email = find_personal_email_by_pattern(decision_maker_name, website_url)
        if pattern_email:
            if pattern_email not in valid_emails:
                valid_emails.insert(0, pattern_email)

    # Filter out generic emails if we have a personal one
    personal_emails = [e for e in valid_emails if not any(
        e.lower().startswith(p) for p in ["info@", "contact@", "hello@", "iletisim@", "bilgi@", "sales@", "satis@"]
    )]
    best_email = personal_emails[0] if personal_emails else (pick_best_email(valid_emails) if valid_emails else "")

    # Determine if this lead needs manual review
    needs_manual = needs_enrichment and not best_email and not decision_maker_name

    return {
        "page_text": all_text[:10000],
        "emails_found": valid_emails,
        "best_email": best_email,
        "decision_maker": decision_maker_name,
        "decision_maker_title": decision_maker_title,
        "decision_maker_linkedin": decision_maker_linkedin,
        "decision_maker_bio": decision_maker_bio,
        "needs_manual_review": needs_manual,
    }


def generate_email_patterns(first_name, last_name, domain):
    """Generate likely email patterns from name + domain."""
    if not first_name or not domain:
        return []

    first = first_name.lower().strip()
    last = last_name.lower().strip() if last_name else ""

    # Turkish char normalization
    tr_map = str.maketrans({
        '\u00e7': 'c', '\u011f': 'g', '\u0131': 'i', '\u00f6': 'o',
        '\u015f': 's', '\u00fc': 'u', '\u00c7': 'c', '\u011e': 'g',
        '\u0130': 'i', '\u00d6': 'o', '\u015e': 's', '\u00dc': 'u',
    })
    first = first.translate(tr_map)
    last = last.translate(tr_map)

    patterns = []
    if last:
        patterns = [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{first[0]}{last}@{domain}",
            f"{first}_{last}@{domain}",
            f"{first[0]}.{last}@{domain}",
            f"{last}.{first}@{domain}",
            f"{first}@{domain}",
            f"{last}@{domain}",
            f"{first[0]}{last[0]}@{domain}",
        ]
    else:
        patterns = [f"{first}@{domain}"]

    return patterns


def find_personal_email_by_pattern(decision_maker_name, website_url):
    """Try to find decision maker's personal email using pattern guessing + SMTP."""
    if not decision_maker_name or not website_url:
        return ""

    domain = urlparse(website_url).netloc.replace("www.", "")
    if not domain:
        return ""

    parts = decision_maker_name.strip().split()
    if len(parts) < 1:
        return ""

    first_name = parts[0]
    last_name = parts[-1] if len(parts) > 1 else ""

    patterns = generate_email_patterns(first_name, last_name, domain)
    print(f"    Pattern search: trying {len(patterns)} patterns for {decision_maker_name}@{domain}")

    from pipeline.email_validator import validate_email, verify_smtp

    for email_guess in patterns:
        is_valid, reason = validate_email(email_guess, skip_smtp=True)
        if not is_valid:
            continue

        exists, smtp_reason = verify_smtp(email_guess, timeout=8)
        if exists is True and smtp_reason == "verified":
            print(f"    FOUND via pattern: {email_guess} (SMTP verified)")
            return email_guess
        elif exists is True and smtp_reason == "catch_all":
            # Catch-all server - can't confirm, but first pattern is likely correct
            print(f"    Likely match (catch-all): {email_guess}")
            return email_guess

    print(f"    No pattern match found for {decision_maker_name}@{domain}")
    return ""


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
            new_status = "needs_manual_review" if result.get("needs_manual_review") else "scraped"
            db.execute(
                """UPDATE leads SET
                    emails_found = ?,
                    decision_maker = ?,
                    decision_maker_title = ?,
                    decision_maker_email = ?,
                    decision_maker_linkedin = ?,
                    decision_maker_bio = ?,
                    scrape_status = 'success',
                    status = ?,
                    scraped_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (
                    emails_json,
                    result["decision_maker"],
                    result["decision_maker_title"],
                    result["best_email"],
                    result.get("decision_maker_linkedin", ""),
                    result.get("decision_maker_bio", ""),
                    new_status,
                    lead["id"],
                ),
            )
            # Store page text for analysis
            db.execute(
                "UPDATE leads SET analysis_raw = ? WHERE id = ?",
                (result["page_text"], lead["id"]),
            )
            scraped += 1
            print(f"  Emails found: {result['emails_found']}")
            print(f"  Best email: {result['best_email']}")
            if new_status == "needs_manual_review":
                print(f"  Status: needs_manual_review (no decision maker or email found)")

        db.commit()
        log_activity(db, "lead_scraped", "lead", lead["id"], f"Emails: {len(result.get('emails_found', []))}")

    db.close()
    print(f"\nScraping complete. Scraped {scraped}/{len(leads)} leads.")
    return scraped


if __name__ == "__main__":
    print("=== ATAOL AI Techs Web Scraper ===\n")
    run_scraping(max_leads=5)
