import re
import asyncio
from models import EmailStatusEnum
# import dns.asyncresolver # In a real app we'd use this for async dns lookup

async def verify_email(email: str) -> str:
    """
    Asynchronously verifies an email address using Regex, mock async DNS (MX), 
    and a simulated SMTP handshake.
    """
    # 1. Regex check
    email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    if not email_regex.match(email):
        return EmailStatusEnum.Invalid.value

    domain = email.split("@")[1]

    # 2. Mock Async DNS MX Record lookup
    # Simulate DNS network latency (e.g. looking up MX records)
    await asyncio.sleep(0.5) 
    
    # Simulate missing MX records for specific domains
    if domain in ["invalid-domain.com", "nodns.org", "fake.com"]:
        return EmailStatusEnum.Invalid.value
        
    # 3. Simulate SMTP Handshake
    # Connect, EHLO, MAIL FROM, RCPT TO, QUIT
    # We simulate this network interaction latency here.
    await asyncio.sleep(1.2) 
    
    # Randomly simulate different server responses for the prototype based on rules.
    # In reality, catching 250 OK or 550 User unknown.
    
    if "catchall" in domain:
        return EmailStatusEnum.Catch_all.value
        
    if email.startswith("fake_") or email.startswith("bounce_"):
        return EmailStatusEnum.Invalid.value
        
    return EmailStatusEnum.Valid.value
