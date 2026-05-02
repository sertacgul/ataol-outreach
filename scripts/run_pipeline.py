"""
Run the ATAOL AI Techs outreach pipeline manually.
Usage: python scripts/run_pipeline.py [step]

Steps: research, scrape, analyze, generate, send, all
"""

import sys
import os

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db

init_db()


def run_step(step):
    if step in ("research", "all"):
        print("\n=== Step 1: Research ===\n")
        from pipeline.research import run_research
        run_research(max_queries=3, region="tr-tr", language="tr")
        run_research(max_queries=2, region="wt-wt", language="en")

    if step in ("scrape", "all"):
        print("\n=== Step 2: Scrape ===\n")
        from pipeline.scraper import run_scraping
        run_scraping(max_leads=10)

    if step in ("analyze", "all"):
        print("\n=== Step 3: Analyze ===\n")
        from pipeline.analyzer import run_analysis
        run_analysis(max_leads=10)

    if step in ("generate", "all"):
        print("\n=== Step 4: Generate Emails ===\n")
        from pipeline.email_generator import run_email_generation
        run_email_generation(max_leads=10)

    if step in ("send", "all"):
        print("\n=== Step 5: Send Approved ===\n")
        from pipeline.sender import send_approved_batch
        from database import get_db
        db = get_db()
        send_approved_batch(db)
        db.close()


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    valid = ("research", "scrape", "analyze", "generate", "send", "all")
    if step not in valid:
        print(f"Usage: python scripts/run_pipeline.py [{' | '.join(valid)}]")
        sys.exit(1)
    run_step(step)
