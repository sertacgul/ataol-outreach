import json
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db, log_activity

bp = Blueprint("main", __name__)


def get_stats(db):
    total_leads = db.execute("SELECT COUNT(*) c FROM leads WHERE is_excluded = 0").fetchone()["c"]
    analyzed = db.execute("SELECT COUNT(*) c FROM leads WHERE analysis_status = 'success'").fetchone()["c"]
    pending_review = db.execute("SELECT COUNT(*) c FROM emails WHERE status = 'pending_review'").fetchone()["c"]
    approved = db.execute("SELECT COUNT(*) c FROM emails WHERE status = 'approved'").fetchone()["c"]
    total_sent = db.execute("SELECT COUNT(*) c FROM emails WHERE status = 'sent'").fetchone()["c"]
    sent_today = db.execute(
        "SELECT COUNT(*) c FROM daily_send_log WHERE sent_date = ?", (date.today().isoformat(),)
    ).fetchone()["c"]
    return {
        "total_leads": total_leads,
        "analyzed": analyzed,
        "pending_review": pending_review,
        "approved": approved,
        "total_sent": total_sent,
        "sent_today": sent_today,
    }


def get_pipeline_stats(db):
    stats = get_stats(db)
    stats["unscraped"] = db.execute(
        "SELECT COUNT(*) c FROM leads WHERE scrape_status = 'pending' AND is_excluded = 0"
    ).fetchone()["c"]
    stats["unanalyzed"] = db.execute(
        "SELECT COUNT(*) c FROM leads WHERE scrape_status = 'success' AND analysis_status = 'pending' AND is_excluded = 0"
    ).fetchone()["c"]
    stats["no_email"] = db.execute(
        """SELECT COUNT(*) c FROM leads
           WHERE analysis_status = 'success' AND is_excluded = 0
             AND id NOT IN (SELECT lead_id FROM emails)"""
    ).fetchone()["c"]
    return stats


# ---- Dashboard ----

@bp.route("/")
def index():
    db = get_db()
    stats = get_stats(db)
    activities = db.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 20").fetchall()
    db.close()
    return render_template("index.html", stats=stats, activities=activities)


# ---- Leads ----

@bp.route("/leads")
def leads_list():
    db = get_db()
    status = request.args.get("status", "all")
    if status == "all":
        leads = db.execute("SELECT * FROM leads WHERE is_excluded = 0 ORDER BY discovered_at DESC").fetchall()
    else:
        leads = db.execute(
            "SELECT * FROM leads WHERE status = ? AND is_excluded = 0 ORDER BY discovered_at DESC", (status,)
        ).fetchall()
    db.close()
    return render_template("leads.html", leads=leads, filter=status)


@bp.route("/leads/<int:lead_id>")
def lead_detail(lead_id):
    db = get_db()
    lead = db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        db.close()
        flash("Lead not found.", "error")
        return redirect(url_for("main.leads_list"))

    pain_points = []
    service_match = []
    try:
        pain_points = json.loads(lead["pain_points"]) if lead["pain_points"] else []
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        service_match = json.loads(lead["service_match"]) if lead["service_match"] else []
    except (json.JSONDecodeError, TypeError):
        pass

    emails = db.execute("SELECT * FROM emails WHERE lead_id = ? ORDER BY generated_at DESC", (lead_id,)).fetchall()
    db.close()
    return render_template("lead_detail.html", lead=lead, pain_points=pain_points, service_match=service_match, emails=emails)


@bp.route("/leads/<int:lead_id>/exclude", methods=["POST"])
def exclude_lead(lead_id):
    db = get_db()
    db.execute("UPDATE leads SET is_excluded = 1, exclude_reason = 'manual' WHERE id = ?", (lead_id,))
    db.commit()
    log_activity(db, "lead_excluded", "lead", lead_id)
    db.close()
    flash("Lead excluded.", "success")
    return redirect(url_for("main.leads_list"))


# ---- Emails ----

@bp.route("/emails/pending")
def emails_pending():
    db = get_db()
    emails = db.execute(
        """SELECT e.*, l.company_name FROM emails e
           LEFT JOIN leads l ON e.lead_id = l.id
           WHERE e.status = 'pending_review' ORDER BY e.generated_at DESC"""
    ).fetchall()
    db.close()
    return render_template("pending_emails.html", emails=emails, title="Pending Review", status_filter="pending_review")


@bp.route("/emails/approved")
def emails_approved():
    db = get_db()
    emails = db.execute(
        """SELECT e.*, l.company_name FROM emails e
           LEFT JOIN leads l ON e.lead_id = l.id
           WHERE e.status = 'approved' ORDER BY e.approved_at DESC"""
    ).fetchall()
    db.close()
    return render_template("pending_emails.html", emails=emails, title="Approved", status_filter="approved")


@bp.route("/emails/sent")
def emails_sent():
    db = get_db()
    emails = db.execute(
        """SELECT e.*, l.company_name FROM emails e
           LEFT JOIN leads l ON e.lead_id = l.id
           WHERE e.status = 'sent' ORDER BY e.sent_at DESC"""
    ).fetchall()
    db.close()
    return render_template("pending_emails.html", emails=emails, title="Sent", status_filter="sent")


@bp.route("/emails/rejected")
def emails_rejected():
    db = get_db()
    emails = db.execute(
        """SELECT e.*, l.company_name FROM emails e
           LEFT JOIN leads l ON e.lead_id = l.id
           WHERE e.status = 'rejected' ORDER BY e.reviewed_at DESC"""
    ).fetchall()
    db.close()
    return render_template("pending_emails.html", emails=emails, title="Rejected", status_filter="rejected")


@bp.route("/emails/<int:email_id>")
def email_detail(email_id):
    db = get_db()
    email = db.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    if not email:
        db.close()
        flash("Email not found.", "error")
        return redirect(url_for("main.emails_pending"))

    lead = db.execute("SELECT * FROM leads WHERE id = ?", (email["lead_id"],)).fetchone()
    pain_points = []
    if lead:
        try:
            pain_points = json.loads(lead["pain_points"]) if lead["pain_points"] else []
        except (json.JSONDecodeError, TypeError):
            pass
    db.close()
    return render_template("email_detail.html", email=email, lead=lead, pain_points=pain_points)


@bp.route("/emails/<int:email_id>/approve", methods=["POST"])
def approve_email(email_id):
    db = get_db()
    db.execute(
        "UPDATE emails SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP, approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (email_id,),
    )
    db.commit()
    log_activity(db, "email_approved", "email", email_id)
    db.close()
    flash("Email approved and queued for sending.", "success")
    return redirect(url_for("main.emails_pending"))


@bp.route("/emails/<int:email_id>/reject", methods=["POST"])
def reject_email(email_id):
    db = get_db()
    db.execute(
        "UPDATE emails SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP, rejection_reason = 'manual' WHERE id = ?",
        (email_id,),
    )
    db.commit()
    log_activity(db, "email_rejected", "email", email_id)
    db.close()
    flash("Email rejected.", "info")
    return redirect(url_for("main.emails_pending"))


@bp.route("/emails/<int:email_id>/edit", methods=["POST"])
def edit_email(email_id):
    db = get_db()
    subject = request.form.get("subject", "")
    body_html = request.form.get("body_html", "")
    body_text = request.form.get("body_text", "")
    db.execute(
        "UPDATE emails SET subject = ?, body_html = ?, body_text = ? WHERE id = ?",
        (subject, body_html, body_text, email_id),
    )
    db.commit()
    log_activity(db, "email_edited", "email", email_id)
    db.close()
    flash("Email updated.", "success")
    return redirect(url_for("main.email_detail", email_id=email_id))


@bp.route("/emails/<int:email_id>/regenerate", methods=["POST"])
def regenerate_email(email_id):
    db = get_db()
    email = db.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    if not email:
        db.close()
        flash("Email not found.", "error")
        return redirect(url_for("main.emails_pending"))

    lead = db.execute("SELECT * FROM leads WHERE id = ?", (email["lead_id"],)).fetchone()
    if not lead:
        db.close()
        flash("Lead not found.", "error")
        return redirect(url_for("main.emails_pending"))

    try:
        from pipeline.email_generator import generate_email
        email_data = generate_email(dict(lead), None, lead["language"])
        if email_data.get("error"):
            flash(f"Regeneration failed: {email_data['error']}", "error")
        else:
            db.execute(
                "UPDATE emails SET subject = ?, body_html = ?, body_text = ? WHERE id = ?",
                (email_data["subject"], email_data["body_html"], email_data["body_text"], email_id),
            )
            db.commit()
            log_activity(db, "email_regenerated", "email", email_id)
            flash("Email regenerated with AI.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "error")

    db.close()
    return redirect(url_for("main.email_detail", email_id=email_id))


# ---- Pipeline ----

@bp.route("/pipeline")
def pipeline():
    db = get_db()
    stats = get_pipeline_stats(db)
    db.close()
    return render_template("pipeline.html", stats=stats)


@bp.route("/pipeline/research", methods=["POST"])
def run_research_route():
    language = request.form.get("language", "tr")
    max_queries = int(request.form.get("max_queries", 3))
    try:
        from pipeline.research import run_research
        region = "tr-tr" if language == "tr" else "wt-wt"
        count = run_research(max_queries=max_queries, region=region, language=language)
        flash(f"Research complete. Found {count} new leads.", "success")
    except Exception as e:
        flash(f"Research error: {str(e)}", "error")
    return redirect(url_for("main.pipeline"))


@bp.route("/pipeline/scrape", methods=["POST"])
def run_scrape_route():
    max_leads = int(request.form.get("max_leads", 10))
    try:
        from pipeline.scraper import run_scraping
        count = run_scraping(max_leads=max_leads)
        flash(f"Scraping complete. Scraped {count} leads.", "success")
    except Exception as e:
        flash(f"Scraping error: {str(e)}", "error")
    return redirect(url_for("main.pipeline"))


@bp.route("/pipeline/analyze", methods=["POST"])
def run_analyze_route():
    max_leads = int(request.form.get("max_leads", 10))
    try:
        from pipeline.analyzer import run_analysis
        count = run_analysis(max_leads=max_leads)
        flash(f"Analysis complete. Analyzed {count} leads.", "success")
    except Exception as e:
        flash(f"Analysis error: {str(e)}", "error")
    return redirect(url_for("main.pipeline"))


@bp.route("/pipeline/generate", methods=["POST"])
def run_generate_route():
    max_leads = int(request.form.get("max_leads", 10))
    try:
        from pipeline.email_generator import run_email_generation
        count = run_email_generation(max_leads=max_leads)
        flash(f"Email generation complete. Generated {count} emails.", "success")
    except Exception as e:
        flash(f"Generation error: {str(e)}", "error")
    return redirect(url_for("main.pipeline"))


@bp.route("/pipeline/send", methods=["POST"])
def run_send_route():
    try:
        from pipeline.sender import send_approved_batch
        db = get_db()
        count = send_approved_batch(db)
        db.close()
        flash(f"Sent {count} emails.", "success")
    except Exception as e:
        flash(f"Send error: {str(e)}", "error")
    return redirect(url_for("main.pipeline"))


@bp.route("/pipeline/full", methods=["POST"])
def run_full_pipeline():
    results = []
    try:
        from pipeline.research import run_research
        count = run_research(max_queries=2, region="tr-tr", language="tr")
        results.append(f"Research: {count} new leads")
    except Exception as e:
        results.append(f"Research error: {e}")

    try:
        from pipeline.scraper import run_scraping
        count = run_scraping(max_leads=10)
        results.append(f"Scraping: {count} leads scraped")
    except Exception as e:
        results.append(f"Scraping error: {e}")

    try:
        from pipeline.analyzer import run_analysis
        count = run_analysis(max_leads=10)
        results.append(f"Analysis: {count} leads analyzed")
    except Exception as e:
        results.append(f"Analysis error: {e}")

    try:
        from pipeline.email_generator import run_email_generation
        count = run_email_generation(max_leads=10)
        results.append(f"Emails: {count} generated")
    except Exception as e:
        results.append(f"Email generation error: {e}")

    flash(" | ".join(results), "success")
    return redirect(url_for("main.pipeline"))
