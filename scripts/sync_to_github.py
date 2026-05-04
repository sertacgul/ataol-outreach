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
APPROVALS_FILENAME = "approvals.json"


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


def import_full_from_gist():
    """Import all email and lead data from gist into local DB (for fresh CI runners)."""
    if not GIST_ID:
        print("GIST_ID not configured. Skipping full import.")
        return

    result = subprocess.run(
        ["gh", "gist", "view", GIST_ID, "--filename", GIST_FILENAME, "--raw"],
        capture_output=True, text=True, encoding="utf-8",
    )

    if result.returncode != 0:
        print(f"Gist fetch error: {result.stderr}")
        return

    data = json.loads(result.stdout)
    db = get_db()

    # Get DB column names for safe insertion
    lead_cols = [row[1] for row in db.execute("PRAGMA table_info(leads)").fetchall()]
    email_cols = [row[1] for row in db.execute("PRAGMA table_info(emails)").fetchall()]

    leads_imported = 0
    for lead in data.get("leads", []):
        lead_id = lead.get("id")
        if not lead_id:
            continue
        if db.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone():
            continue
        cols = [c for c in lead.keys() if c in lead_cols]
        vals = [json.dumps(lead[c]) if isinstance(lead[c], (list, dict)) else lead[c] for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        try:
            db.execute(f"INSERT INTO leads ({','.join(cols)}) VALUES ({placeholders})", vals)
            leads_imported += 1
        except Exception as e:
            print(f"  Lead #{lead_id} import error: {e}")

    emails_imported = 0
    for email in data.get("emails", []):
        email_id = email.get("id")
        if not email_id:
            continue
        if db.execute("SELECT 1 FROM emails WHERE id = ?", (email_id,)).fetchone():
            continue
        cols = [c for c in email.keys() if c in email_cols]
        vals = [json.dumps(email[c]) if isinstance(email[c], (list, dict)) else email[c] for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        try:
            db.execute(f"INSERT INTO emails ({','.join(cols)}) VALUES ({placeholders})", vals)
            emails_imported += 1
        except Exception as e:
            print(f"  Email #{email_id} import error: {e}")

    db.commit()
    db.close()
    print(f"Full import: {leads_imported} leads, {emails_imported} emails from gist.")


def import_approvals_from_gist():
    """Read approvals.json from gist and apply status changes to local DB."""
    if not GIST_ID:
        print("GIST_ID not configured. Skipping pull.")
        return 0

    result = subprocess.run(
        ["gh", "gist", "view", GIST_ID, "--filename", APPROVALS_FILENAME, "--raw"],
        capture_output=True, text=True, encoding="utf-8",
    )

    if result.returncode != 0:
        print(f"No approvals file in gist (normal if none approved yet).")
        return 0

    data = json.loads(result.stdout)
    statuses = data.get("statuses", {})
    if not statuses:
        print("No status changes in approvals.")
        return 0

    db = get_db()
    updated = 0

    for email_id_str, new_status in statuses.items():
        email_id = int(email_id_str)
        if new_status not in ("approved", "rejected"):
            continue

        current = db.execute("SELECT status FROM emails WHERE id = ?", (email_id,)).fetchone()
        if not current:
            continue

        old_status = current["status"]
        if old_status == "pending_review":
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
    print(f"Imported {updated} status changes from approvals.")
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
