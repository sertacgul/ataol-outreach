"""
Email validation module.
- Filters KEP (Kayitli Elektronik Posta) addresses
- Filters placeholder/invalid patterns
- Verifies domain has valid MX records via DNS
- SMTP RCPT TO verification (checks if mailbox actually exists)
- Validates email format
"""

import re
import socket
import smtplib
import dns.resolver

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
    "acme.com", "placeholder.com",
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
    "musteri@", "musterihizmetleri@", "customer@", "customerservice@", "customercare@",
    "abuse@", "spam@", "security@", "webmaster@",
    "press@", "media@", "pr@", "basin@",
    "careers@", "jobs@", "recruitment@", "ik@", "insankaynaklari@", "join@",
    "privacy@", "legal@", "hukuk@", "kvkk@", "gdpr@",
    "billing@", "invoice@", "fatura@", "muhasebe@", "accounting@",
    "noreply@", "no-reply@", "donotreply@",
    "giving@", "donate@", "donations@",
    "akademi@", "academy@", "training@", "egitim@",
    "feedback@", "survey@", "anket@",
    "newsletter@", "subscribe@",
    "events@", "event@", "etkinlik@",
    "dev@", "devops@", "engineering@", "tech@",
    "patientsupport@", "patient@",
    "community@", "forum@",
    "demo@", "trial@",
    "orders@", "siparis@", "shop@",
    "reservations@", "booking@", "rezervasyon@",
]

# Generic/low-value prefixes (deprioritize, don't exclude)
GENERIC_PREFIXES = [
    "info@", "contact@", "hello@", "hi@",
    "iletisim@", "bilgi@",
    "sales@", "satis@", "marketing@",
]

# Cache for MX lookups and SMTP checks
_mx_cache = {}
_smtp_cache = {}


def is_kep_address(email):
    """Check if email is a KEP (Kayitli Elektronik Posta) address."""
    domain = email.split("@")[-1].lower()
    return any(domain.endswith(kep) for kep in KEP_DOMAINS)


def has_invalid_pattern(email):
    """Check if email matches known invalid/placeholder patterns."""
    email_lower = email.lower()
    for pattern in INVALID_PATTERNS:
        if pattern in email_lower:
            return True
    for ext in INVALID_EXTENSIONS:
        if email_lower.endswith(ext):
            return True
    return False


def is_valid_format(email):
    """Check basic email format."""
    return bool(EMAIL_REGEX.match(email))


def get_mx_hosts(domain):
    """Get MX hosts for a domain using dnspython. Returns sorted list of (priority, host)."""
    if domain in _mx_cache:
        return _mx_cache[domain]

    mx_hosts = []
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        for rdata in answers:
            mx_hosts.append((rdata.preference, str(rdata.exchange).rstrip('.')))
        mx_hosts.sort(key=lambda x: x[0])
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
        pass

    _mx_cache[domain] = mx_hosts
    return mx_hosts


def has_mx_record(domain):
    """Check if domain has MX records."""
    return len(get_mx_hosts(domain)) > 0


def verify_smtp(email, timeout=10):
    """
    Verify email exists via SMTP RCPT TO.
    Returns (exists, reason):
      - (True, "verified") - mailbox confirmed
      - (True, "catch_all") - server accepts everything, can't confirm
      - (False, "rejected") - server explicitly rejected
      - (None, "inconclusive") - couldn't connect or timed out
    """
    if email in _smtp_cache:
        return _smtp_cache[email]

    domain = email.split("@")[-1]
    mx_hosts = get_mx_hosts(domain)

    if not mx_hosts:
        result = (False, "no_mx")
        _smtp_cache[email] = result
        return result

    for _, mx_host in mx_hosts[:2]:
        try:
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(mx_host, 25)
            smtp.helo("ataolai.tech")

            smtp.mail("verify@ataolai.tech")
            code, _ = smtp.rcpt(email)

            # Check catch-all: try a random address that shouldn't exist
            fake_email = f"zqxwce_nonexistent_12345@{domain}"
            catch_code, _ = smtp.rcpt(fake_email)

            smtp.quit()

            if code == 250:
                if catch_code == 250:
                    result = (True, "catch_all")
                else:
                    result = (True, "verified")
            elif code >= 500:
                result = (False, "rejected")
            else:
                result = (None, "inconclusive")

            _smtp_cache[email] = result
            return result

        except (smtplib.SMTPException, socket.error, socket.timeout, OSError):
            continue

    result = (None, "inconclusive")
    _smtp_cache[email] = result
    return result


def is_blocked_prefix(email):
    """Check if email has a blocked prefix."""
    email_lower = email.lower()
    return any(email_lower.startswith(prefix) for prefix in BLOCKED_PREFIXES)


def validate_email(email, skip_smtp=False):
    """
    Validate an email address. Returns (is_valid, reason).
    """
    if not email or not email.strip():
        return False, "empty"

    email = email.strip().lower()

    if not is_valid_format(email):
        return False, "invalid_format"

    if is_kep_address(email):
        return False, "kep_address"

    if is_blocked_prefix(email):
        return False, "blocked_prefix"

    if has_invalid_pattern(email):
        return False, "invalid_pattern"

    domain = email.split("@")[-1]
    if not has_mx_record(domain):
        return False, "no_mx_record"

    if not skip_smtp:
        exists, smtp_reason = verify_smtp(email)
        if exists is False:
            return False, f"smtp_{smtp_reason}"

    return True, "valid"


def validate_and_filter_emails(emails, skip_smtp=False):
    """
    Validate a list of emails. Returns (valid_emails, rejected_with_reasons).
    """
    valid = []
    rejected = []

    for email in emails:
        is_valid, reason = validate_email(email, skip_smtp=skip_smtp)
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
    0: unverified via SMTP
    """
    local = email.split("@")[0].lower()
    role_keywords = ["ceo", "founder", "cto", "coo", "director", "manager", "kurucu", "genel", "baskan", "owner", "md", "gm"]

    base_score = 1
    if any(kw in local for kw in role_keywords):
        base_score = 2
    elif not is_generic_email(email):
        base_score = 3

    # Boost if SMTP verified
    exists, reason = verify_smtp(email)
    if exists is True and reason == "verified":
        return base_score + 1
    elif exists is False:
        return 0

    return base_score


def pick_best_email(emails):
    """Pick the best email from a list, preferring verified personal > role > generic."""
    if not emails:
        return ""
    valid, _ = validate_and_filter_emails(emails, skip_smtp=True)
    if not valid:
        return ""
    scored = sorted(valid, key=score_email, reverse=True)
    return scored[0]
