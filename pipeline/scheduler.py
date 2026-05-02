"""
ATAOL AI Techs Outreach Scheduler

Runs the outreach pipeline on a schedule:
- Morning (09:00): Research, scrape, analyze, generate emails
- Afternoon (14:00): Send approved emails
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import schedule
from database import get_db


def morning_pipeline():
    print("\n=== Morning Pipeline Starting ===\n")

    try:
        from pipeline.research import run_research
        run_research(max_queries=2, region="tr-tr", language="tr")
        run_research(max_queries=1, region="wt-wt", language="en")
    except Exception as e:
        print(f"Research error: {e}")

    try:
        from pipeline.scraper import run_scraping
        run_scraping(max_leads=10)
    except Exception as e:
        print(f"Scraping error: {e}")

    try:
        from pipeline.analyzer import run_analysis
        run_analysis(max_leads=10)
    except Exception as e:
        print(f"Analysis error: {e}")

    try:
        from pipeline.email_generator import run_email_generation
        run_email_generation(max_leads=10)
    except Exception as e:
        print(f"Email generation error: {e}")

    print("\n=== Morning Pipeline Complete ===\n")


def afternoon_sender():
    print("\n=== Afternoon Sender Starting ===\n")
    try:
        from pipeline.sender import send_approved_batch
        db = get_db()
        send_approved_batch(db)
        db.close()
    except Exception as e:
        print(f"Send error: {e}")
    print("\n=== Afternoon Sender Complete ===\n")


def start_scheduler():
    print("ATAOL AI Techs Outreach Scheduler")
    print("Schedule:")
    print("  - 09:00 Mon-Fri: Research + Analyze + Generate")
    print("  - 14:00 Daily: Send approved emails")
    print("\nWaiting for scheduled tasks...\n")

    schedule.every().monday.at("09:00").do(morning_pipeline)
    schedule.every().tuesday.at("09:00").do(morning_pipeline)
    schedule.every().wednesday.at("09:00").do(morning_pipeline)
    schedule.every().thursday.at("09:00").do(morning_pipeline)
    schedule.every().friday.at("09:00").do(morning_pipeline)

    schedule.every().day.at("14:00").do(afternoon_sender)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        print("Running pipeline now...\n")
        morning_pipeline()
    else:
        start_scheduler()
