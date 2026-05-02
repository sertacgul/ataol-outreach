"""
Sync local SQLite data to/from GitHub Gist for the dashboard.

Usage:
  python scripts/sync_to_github.py push   - Export local data to gist
  python scripts/sync_to_github.py pull   - Import approvals from gist to local
  python scripts/sync_to_github.py sync   - Full sync (pull then push)
"""

import sys
import os
import json
import re
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db

GIST_ID = os.getenv("GIST_ID", "")
GIST_FILENAME = "emails.json"


def compact_html(html):
    if not html:
        return ""
    html = re.sub(r'\n\s*', '', html)
    html = re.sub(r'>\s+<', '><', html)
    html = re.sub(r'\s{2,}', ' ', html)
    return html.strip()


def export_data_to_gist():
    if not GIST_ID:
        print("GIST_ID not configured. Skipping push.")
        return

    db = get_db()

    emails = db.execute("SELECT * FROM emails ORDER BY generated_at DESC").fetchall()
    emails_list = []
    for row in emails:
        e = dict(row)
        e.pop("prompt_used", None)
        e["body_html"] = compact_html(e.get("body_html", ""))
        e["body_text"] = (e.get("body_text", "") or "")[:500]
        emails_list.append(e)

    leads = db.execute("SELECT * FROM leads WHERE is_excluded = 0 ORDER BY discovered_at DESC").fetchall()
    leads_list = []
    for row in leads:
        l = dict(row)
        l.pop("analysis_raw", None)
        l.pop("prompt_used", None)
        leads_list.append(l)

    db.close()

    data = {
        "emails": emails_list,
        "leads": leads_list,
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    }

    json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'), default=str)
    print(f"Payload: {len(json_str)} bytes, {len(emails_list)} emails, {len(leads_list)} leads")

    import tempfile
    path = os.path.join(tempfile.gettempdir(), "ataol_gist_data.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)

    result = subprocess.run(
        ["gh", "gist", "edit", GIST_ID, "--filename", GIST_FILENAME, path],
        capture_output=True, text=True, encoding="utf-8",
    )

    if result.returncode == 0:
        print(f"Pushed successfully.")
    else:
        print(f"Gist update error: {result.stderr[:300]}")


def import_approvals_from_gist():
    if not GIST_ID:
        print("GIST_ID not configured. Skipping pull.")
        return 0

    result = subprocess.run(
        ["gh", "gist", "view", GIST_ID, "--filename", GIST_FILENAME, "--raw"],
        capture_output=True, text=True, encoding="utf-8",
    )

    if result.returncode != 0:
        print(f"Gist fetch error: {result.stderr}")
        return 0

    data = json.loads(result.stdout)
    db = get_db()
    updated = 0

    for email in data.get("emails", []):
        email_id = email.get("id")
        new_status = email.get("status")
        if not email_id or not new_status:
            continue

        current = db.execute("SELECT status FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not current:
            continue

        old_status = current["status"]

        if old_status == "pending_review" and new_status in ("approved", "rejected"):
            db.execute(
                "UPDATE emails SET status = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_status, email_id),
            )
            if new_status == "approved":
                db.execute(
                    "UPDATE emails SET approved_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (email_id,),
                )
            updated += 1
            print(f"  Email #{email_id}: {old_status} -> {new_status}")

    db.commit()
    db.close()
    print(f"Imported {updated} status changes from gist.")
    return updated


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "push"

    if action == "push":
        print("=== Pushing data to GitHub Gist ===")
        export_data_to_gist()
    elif action == "pull":
        print("=== Pulling approvals from GitHub Gist ===")
        import_approvals_from_gist()
    elif action == "sync":
        print("=== Full sync ===")
        import_approvals_from_gist()
        export_data_to_gist()
    else:
        print("Usage: python scripts/sync_to_github.py [push|pull|sync]")
