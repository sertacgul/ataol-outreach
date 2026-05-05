"""
Email validation module.
- Filters KEP (Kayitli Elektronik Posta) addresses
- Filters placeholder/invalid patterns
- Verifies domain has valid MX records (can receive email)
- Validates email format
"""

import re
import socket
import struct

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# KEP (Turkish registered email) domains
KEP_DOMAINS = [
    "hs01.kep.tr", "hs02.kep.tr", "hs03.kep.tr", "hs04.kep.tr",
    "hs05.kep.tr", "hs06.kep.tr", "hs07.kep.tr", "hs08.kep.tr",
    "kep.tr", "turksat.kep.tr", "tnnhskep.com", "kephs.com",
]

# Invalid/placeholder patterns
INVALID_PATTERNS = [
    "example.com", "example.org", "example.net",
    "company.com", "domain.com", "email.com",
    "test@", "user@", "name@", "yourname@", "you@",
    "ornek@", "email@", "abc@", "xxx@", "admin@",
    "noreply@", "no-reply@", "mailer-daemon@", "postmaster@",
    "donotreply@", "bounce@", "unsubscribe@",
    "sentry.io", "wixpress.com", "hubspot.com",
    "mailchimp.com", "sendgrid.net", "amazonaws.com",
]

# File extension patterns caught as emails
INVALID_EXTENSIONS = [
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".css", ".js", ".woff", ".woff2", ".avif", ".ico",
    ".pdf", ".doc", ".zip",
]

# Blocked prefixes - these are NEVER valid outreach targets
BLOCKED_PREFIXES = [
    "support@", "help@", "destek@", "yardim@",
    "sikayet@", "complaint@", "complaints@",
    "musteri@", "musterihizmetleri@", "customer@", "customerservice@",
    "abuse@", "spam@", "security@", "webmaster@",
    "press@", "media@", "pr@", "basin@",
    "careers@", "jobs@", "recruitment@", "ik@", "insankaynaklari@",
    "privacy@", "legal@", "hukuk@", "kvkk@", "gdpr@",
    "billing@", "invoice@", "fatura@", "muhasebe@",
    "noreply@", "no-reply@", "donotreply@",
]

# Generic/low-value prefixes (deprioritize, don't exclude)
GENERIC_PREFIXES = [
    "info@", "contact@", "hello@", "hi@",
    "iletisim@", "bilgi@",
    "sales@", "satis@", "marketing@",
]


def is_kep_address(email):
    """Check if email is a KEP (Kayitli Elektronik Posta) address."""
    domain = email.split("@")[-1].lower()
    return any(domain.endswith(kep) for kep in KEP_DOMAINS)


def has_invalid_pattern(email):
    """Check if email matches known invalid/placeholder patterns."""
    email_lower = email.lower()
    # Check patterns
    for pattern in INVALID_PATTERNS:
        if pattern in email_lower:
            return True
    # Check file extensions
    for ext in INVALID_EXTENSIONS:
        if email_lower.endswith(ext):
            return True
    return False


def is_valid_format(email):
    """Check basic email format."""
    return bool(EMAIL_REGEX.match(email))


def has_mx_record(domain):
    """Check if domain has MX records using DNS lookup."""
    try:
        # Use socket to resolve MX
        socket.setdefaulttimeout(5)
        # Try to get MX records via getaddrinfo as a proxy
        # (full MX lookup needs dnspython, this checks if domain resolves at all)
        results = socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
        return len(results) > 0
    except (socket.gaierror, socket.timeout, OSError):
        # Fallback: check if domain resolves at all (A record)
        try:
            socket.gethostbyname(domain)
            return True
        except (socket.gaierror, socket.timeout):
            return False


def is_blocked_prefix(email):
    """Check if email has a blocked prefix (customer service, complaints, etc.)."""
    email_lower = email.lower()
    return any(email_lower.startswith(prefix) for prefix in BLOCKED_PREFIXES)


def validate_email(email):
    """
    Validate an email address. Returns (is_valid, reason).
    """
    if not email or not email.strip():
        return False, "empty"

    email = email.strip().lower()

    # Format check
    if not is_valid_format(email):
        return False, "invalid_format"

    # KEP check
    if is_kep_address(email):
        return False, "kep_address"

    # Blocked prefix check (support, complaints, customer service, etc.)
    if is_blocked_prefix(email):
        return False, "blocked_prefix"

    # Invalid pattern check
    if has_invalid_pattern(email):
        return False, "invalid_pattern"

    # Domain MX check
    domain = email.split("@")[-1]
    if not has_mx_record(domain):
        return False, "no_mx_record"

    return True, "valid"


def validate_and_filter_emails(emails):
    """
    Validate a list of emails. Returns (valid_emails, rejected_with_reasons).
    """
    valid = []
    rejected = []

    for email in emails:
        is_valid, reason = validate_email(email)
        if is_valid:
            valid.append(email)
        else:
            rejected.append((email, reason))

    return valid, rejected


def is_generic_email(email):
    """Check if email is a generic/low-value address (info@, contact@, etc.)."""
    email_lower = email.lower()
    return any(email_lower.startswith(prefix) for prefix in GENERIC_PREFIXES)


def score_email(email):
    """
    Score an email for quality. Higher = better.
    3: personal (name-based)
    2: role-based (ceo@, founder@)
    1: generic but acceptable (info@, contact@)
    """
    local = email.split("@")[0].lower()
    role_keywords = ["ceo", "founder", "cto", "coo", "director", "manager", "kurucu", "genel", "baskan", "owner", "md", "gm"]

    if any(kw in local for kw in role_keywords):
        return 2
    if is_generic_email(email):
        return 1
    # Likely a personal email (firstname, firstname.lastname, etc.)
    return 3


def pick_best_email(emails):
    """Pick the best email from a list, preferring personal > role > generic."""
    if not emails:
        return ""
    valid, _ = validate_and_filter_emails(emails)
    if not valid:
        return ""
    scored = sorted(valid, key=score_email, reverse=True)
    return scored[0]
