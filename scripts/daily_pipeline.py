"""
Daily ATAOL AI Techs Outreach Pipeline

Runs automatically every morning:
1. Pull approvals from GitHub
2. Create follow-up emails
3. Send approved emails
4. Research new companies (TR + EN)
5. Scrape websites for contact info
6. Analyze companies with Gemini (dual-platform)
7. Generate personalized emails (StrategyThrust + ActLedger)
8. Push data to GitHub for review
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler(f"data/pipeline_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

from database import init_db

init_db()


def run_daily():
    log.info("=" * 50)
    log.info("ATAOL AI TECHS - DAILY PIPELINE STARTED")
    log.info("=" * 50)

    log.info("\n--- Step 0: Pull approvals from GitHub ---")
    try:
        from scripts.sync_to_github import import_approvals_from_gist
        import_approvals_from_gist()
    except Exception as e:
        log.error(f"Pull error: {e}")

    log.info("\n--- Step 0.5: Create follow-up emails ---")
    try:
        from pipeline.followup import create_pending_followups
        fu_count = create_pending_followups()
        log.info(f"Created {fu_count} follow-up emails")
    except Exception as e:
        log.error(f"Follow-up error: {e}")

    log.info("\n--- Step 1: Send approved emails ---")
    try:
        from pipeline.sender import send_approved_batch
        from database import get_db
        db = get_db()
        sent = send_approved_batch(db)
        db.close()
        log.info(f"Sent {sent} emails")
    except Exception as e:
        log.error(f"Send error: {e}")

    log.info("\n--- Step 2: Research new companies ---")
    try:
        from pipeline.research import run_research
        tr_count = run_research(max_queries=5, region="tr-tr", language="tr")
        en_count = run_research(max_queries=4, region="wt-wt", language="en")
        log.info(f"Found {tr_count} TR + {en_count} EN = {tr_count + en_count} new leads")
    except Exception as e:
        log.error(f"Research error: {e}")

    log.info("\n--- Step 3: Scrape websites ---")
    try:
        from pipeline.scraper import run_scraping
        scraped = run_scraping(max_leads=50)
        log.info(f"Scraped {scraped} leads")
    except Exception as e:
        log.error(f"Scrape error: {e}")

    log.info("\n--- Step 4: Analyze companies ---")
    try:
        from pipeline.analyzer import run_analysis
        analyzed = run_analysis(max_leads=50)
        log.info(f"Analyzed {analyzed} leads")
    except Exception as e:
        log.error(f"Analyze error: {e}")

    log.info("\n--- Step 5: Generate emails ---")
    try:
        from pipeline.email_generator import run_email_generation
        generated = run_email_generation(max_leads=50)
        log.info(f"Generated {generated} emails")
    except Exception as e:
        log.error(f"Generate error: {e}")

    log.info("\n--- Step 6: Push to GitHub ---")
    try:
        from scripts.sync_to_github import export_data_to_gist
        export_data_to_gist()
    except Exception as e:
        log.error(f"Push error: {e}")

    log.info("\n" + "=" * 50)
    log.info("DAILY PIPELINE COMPLETED")
    log.info("=" * 50)


if __name__ == "__main__":
    run_daily()
