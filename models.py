from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Lead:
    id: Optional[int] = None
    company_name: str = ""
    website: str = ""
    country: str = "TR"
    language: str = "tr"
    industry: str = ""
    company_size: str = ""
    source: str = ""
    search_query: str = ""
    emails_found: str = "[]"
    decision_maker: str = ""
    decision_maker_title: str = ""
    decision_maker_email: str = ""
    company_summary: str = ""
    pain_points: str = "[]"
    service_match: str = "[]"
    analysis_raw: str = ""
    status: str = "discovered"
    scrape_status: str = "pending"
    analysis_status: str = "pending"
    discovered_at: Optional[str] = None
    scraped_at: Optional[str] = None
    analyzed_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_excluded: bool = False
    exclude_reason: str = ""


@dataclass
class Email:
    id: Optional[int] = None
    lead_id: int = 0
    subject: str = ""
    body_html: str = ""
    body_text: str = ""
    language: str = "en"
    to_email: str = ""
    to_name: str = ""
    from_email: str = "sertacgul@strategythrust.com"
    status: str = "pending_review"
    rejection_reason: str = ""
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    generated_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    approved_at: Optional[str] = None
    sent_at: Optional[str] = None
    prompt_used: str = ""
    model_used: str = ""
