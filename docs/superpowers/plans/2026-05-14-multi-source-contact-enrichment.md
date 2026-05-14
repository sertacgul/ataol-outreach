# Multi-Source Contact Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Website scrape'ten kisisel email bulunamayan lead'ler icin LinkedIn ve Crunchbase/website kaynaklarindan karar verici arastirmasi yaparak email bulma oranini artirmak.

**Architecture:** Yeni `pipeline/contact_enrichment.py` modulu, `scraper.py` icinden cagirilir. LinkedIn icin ayri Gemini + Google Search cagrisi, Crunchbase + website icin ayri bir cagri. Sonuclar LinkedIn-oncelikli birlestirilir. Bulunamazsa lead `needs_manual_review` olarak isaretlenir.

**Tech Stack:** Python, google-genai SDK (Gemini + Google Search tool), SQLite

**Spec:** `docs/superpowers/specs/2026-05-14-multi-source-contact-enrichment-design.md`

---

### Task 1: DB migration - yeni kolonlar

**Files:**
- Modify: `database.py:20-100` (init_db CREATE TABLE)

- [ ] **Step 1: Add new columns to leads table schema in init_db**

In `database.py`, add two columns to the `CREATE TABLE IF NOT EXISTS leads` statement, after `decision_maker_email`:

```python
            decision_maker_linkedin TEXT DEFAULT '',
            decision_maker_bio  TEXT DEFAULT '',
```

The full column block around the insertion point becomes:

```python
            decision_maker_email TEXT DEFAULT '',
            decision_maker_linkedin TEXT DEFAULT '',
            decision_maker_bio  TEXT DEFAULT '',
            company_summary     TEXT DEFAULT '',
```

- [ ] **Step 2: Add ALTER TABLE migration for existing databases**

After the `CREATE TABLE` statements and before `conn.commit()`, add migration for existing databases that already have the leads table but lack the new columns:

```python
    # Migrate existing databases: add new columns if missing
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(leads)").fetchall()}
    if "decision_maker_linkedin" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN decision_maker_linkedin TEXT DEFAULT ''")
    if "decision_maker_bio" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN decision_maker_bio TEXT DEFAULT ''")
```

- [ ] **Step 3: Verify migration works**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from database import init_db; init_db()"`

Expected: `Database initialized successfully.` with no errors.

- [ ] **Step 4: Commit**

```bash
git add database.py
git commit -m "feat: add decision_maker_linkedin and decision_maker_bio columns to leads"
```

---

### Task 2: Create contact_enrichment.py - search_linkedin

**Files:**
- Create: `pipeline/contact_enrichment.py`

- [ ] **Step 1: Create module with search_linkedin function**

Create `pipeline/contact_enrichment.py`:

```python
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
```

- [ ] **Step 2: Verify module imports cleanly**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.contact_enrichment import search_linkedin; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/contact_enrichment.py
git commit -m "feat: add contact_enrichment module with search_linkedin"
```

---

### Task 3: Add search_crunchbase_website and merge_results

**Files:**
- Modify: `pipeline/contact_enrichment.py`

- [ ] **Step 1: Add search_crunchbase_website function**

Append after `search_linkedin` in `pipeline/contact_enrichment.py`:

```python
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
```

- [ ] **Step 2: Add merge_results function**

Append after `search_crunchbase_website`:

```python
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
```

- [ ] **Step 3: Verify both functions import cleanly**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.contact_enrichment import search_crunchbase_website, merge_results; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pipeline/contact_enrichment.py
git commit -m "feat: add search_crunchbase_website and merge_results to enrichment"
```

---

### Task 4: Add enrich_contact entry point

**Files:**
- Modify: `pipeline/contact_enrichment.py`

- [ ] **Step 1: Add enrich_contact function**

Append at the end of `pipeline/contact_enrichment.py` (before any `if __name__` block):

```python
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
```

- [ ] **Step 2: Verify the full module**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.contact_enrichment import enrich_contact; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/contact_enrichment.py
git commit -m "feat: add enrich_contact entry point for multi-source enrichment"
```

---

### Task 5: Integrate enrichment into scraper.py

**Files:**
- Modify: `pipeline/scraper.py:128-201` (scrape_company function)

This is the core integration. The changes to `scrape_company()`:
1. Remove `find_contact_with_gemini()` call
2. After email extraction, check if a personal email was found
3. If not, call `enrich_contact()`
4. Use enrichment results for pattern guessing
5. If still no email, mark as `needs_manual_review` via return value

- [ ] **Step 1: Replace find_contact_with_gemini with enrichment logic in scrape_company**

In `scraper.py`, replace the entire `scrape_company` function (lines 128-201) with:

```python
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
```

- [ ] **Step 2: Remove find_contact_with_gemini function**

Delete the `find_contact_with_gemini` function (lines 279-330 in the original file). It's replaced by `contact_enrichment.py`.

- [ ] **Step 3: Verify scraper imports cleanly**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.scraper import scrape_company; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pipeline/scraper.py
git commit -m "feat: integrate contact_enrichment into scraper, remove find_contact_with_gemini"
```

---

### Task 6: Update run_scraping to save new fields and handle needs_manual_review

**Files:**
- Modify: `pipeline/scraper.py:333-397` (run_scraping function)

- [ ] **Step 1: Update the UPDATE query and add needs_manual_review handling**

Replace the `run_scraping` function with:

```python
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
```

- [ ] **Step 2: Verify run_scraping imports cleanly**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.scraper import run_scraping; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/scraper.py
git commit -m "feat: save linkedin/bio fields and handle needs_manual_review in run_scraping"
```

---

### Task 7: Update email_generator to skip needs_manual_review leads

**Files:**
- Modify: `pipeline/email_generator.py:355-358` (SQL query in run_email_generation)

- [ ] **Step 1: Add needs_manual_review to excluded statuses**

In `email_generator.py`, in the `run_email_generation` function, change the SQL query's `NOT IN` clause from:

```python
             AND l.status NOT IN ('completed', 'contacted', 'email_generated')
```

to:

```python
             AND l.status NOT IN ('completed', 'contacted', 'email_generated', 'needs_manual_review')
```

- [ ] **Step 2: Verify email_generator imports cleanly**

Run: `cd C:/Users/serta/ataol-outreach && python -c "from pipeline.email_generator import run_email_generation; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/email_generator.py
git commit -m "feat: skip needs_manual_review leads in email generation"
```

---

### Task 8: End-to-end smoke test

**Files:**
- Read: all modified files for final verification

- [ ] **Step 1: Verify full pipeline import chain**

Run:
```bash
cd C:/Users/serta/ataol-outreach && python -c "
from database import init_db
init_db()
from pipeline.scraper import scrape_company, run_scraping
from pipeline.contact_enrichment import enrich_contact, search_linkedin, search_crunchbase_website, merge_results
from pipeline.email_generator import run_email_generation
print('All imports OK')
"
```

Expected: `Database initialized successfully.` followed by `All imports OK`

- [ ] **Step 2: Test merge_results logic**

Run:
```bash
cd C:/Users/serta/ataol-outreach && python -c "
from pipeline.contact_enrichment import merge_results

# LinkedIn found, Crunchbase found -> LinkedIn wins
r1 = merge_results(
    {'name': 'John Doe', 'title': 'CEO', 'linkedin_url': 'https://linkedin.com/in/johndoe', 'bio': 'Tech leader'},
    {'name': 'Jane Smith', 'title': 'Founder'}
)
assert r1['name'] == 'John Doe'
assert r1['source'] == 'linkedin'
assert r1['linkedin_url'] == 'https://linkedin.com/in/johndoe'

# LinkedIn empty, Crunchbase found -> Crunchbase wins
r2 = merge_results(
    {'name': '', 'title': '', 'linkedin_url': '', 'bio': ''},
    {'name': 'Jane Smith', 'title': 'Founder'}
)
assert r2['name'] == 'Jane Smith'
assert r2['source'] == 'crunchbase'
assert r2['linkedin_url'] == ''

# Both empty -> empty result
r3 = merge_results(
    {'name': '', 'title': '', 'linkedin_url': '', 'bio': ''},
    {'name': '', 'title': ''}
)
assert r3['name'] == ''
assert r3['source'] == ''

print('All merge_results tests passed')
"
```

Expected: `All merge_results tests passed`

- [ ] **Step 3: Test has_personal_email logic**

Run:
```bash
cd C:/Users/serta/ataol-outreach && python -c "
from pipeline.scraper import has_personal_email

assert has_personal_email(['john.doe@company.com']) == True
assert has_personal_email(['info@company.com']) == False
assert has_personal_email(['info@company.com', 'ceo@company.com']) == True
assert has_personal_email(['contact@company.com', 'hello@company.com']) == False
assert has_personal_email([]) == False

print('All has_personal_email tests passed')
"
```

Expected: `All has_personal_email tests passed`

- [ ] **Step 4: Test DB migration with new columns**

Run:
```bash
cd C:/Users/serta/ataol-outreach && python -c "
from database import init_db, get_db
init_db()
db = get_db()
cols = {row[1] for row in db.execute('PRAGMA table_info(leads)').fetchall()}
assert 'decision_maker_linkedin' in cols, 'decision_maker_linkedin column missing'
assert 'decision_maker_bio' in cols, 'decision_maker_bio column missing'
db.close()
print('DB columns verified')
"
```

Expected: `Database initialized successfully.` followed by `DB columns verified`

- [ ] **Step 5: Commit test verification (no file changes, just run log)**

No commit needed - this task is verification only. If all tests pass, the implementation is complete.
