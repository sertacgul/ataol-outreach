import sqlite3
from pathlib import Path
from config import Config


def get_db():
    db_path = Config.DATABASE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name        TEXT NOT NULL,
            website             TEXT UNIQUE NOT NULL,
            country             TEXT DEFAULT 'TR',
            language            TEXT DEFAULT 'tr',
            industry            TEXT DEFAULT '',
            company_size        TEXT DEFAULT '',
            source              TEXT DEFAULT '',
            search_query        TEXT DEFAULT '',
            emails_found        TEXT DEFAULT '[]',
            decision_maker      TEXT DEFAULT '',
            decision_maker_title TEXT DEFAULT '',
            decision_maker_email TEXT DEFAULT '',
            decision_maker_linkedin TEXT DEFAULT '',
            decision_maker_bio  TEXT DEFAULT '',
            company_summary     TEXT DEFAULT '',
            pain_points         TEXT DEFAULT '[]',
            service_match       TEXT DEFAULT '[]',
            analysis_raw        TEXT DEFAULT '',
            status              TEXT DEFAULT 'discovered',
            scrape_status       TEXT DEFAULT 'pending',
            analysis_status     TEXT DEFAULT 'pending',
            discovered_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scraped_at          TIMESTAMP,
            analyzed_at         TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_excluded         BOOLEAN DEFAULT 0,
            exclude_reason      TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS emails (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id             INTEGER NOT NULL REFERENCES leads(id),
            subject             TEXT NOT NULL,
            body_html           TEXT NOT NULL,
            body_text           TEXT NOT NULL,
            language            TEXT DEFAULT 'en',
            to_email            TEXT NOT NULL,
            to_name             TEXT DEFAULT '',
            from_email          TEXT DEFAULT 'sertacgul@strategythrust.com',
            status              TEXT DEFAULT 'pending_review',
            rejection_reason    TEXT DEFAULT '',
            gmail_message_id    TEXT DEFAULT '',
            gmail_thread_id     TEXT DEFAULT '',
            generated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at         TIMESTAMP,
            approved_at         TIMESTAMP,
            sent_at             TIMESTAMP,
            prompt_used         TEXT DEFAULT '',
            model_used          TEXT DEFAULT '',
            email_type          TEXT DEFAULT 'initial',
            followup_count      INTEGER DEFAULT 0,
            parent_email_id     INTEGER
        );

        CREATE TABLE IF NOT EXISTS daily_send_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id    INTEGER NOT NULL REFERENCES emails(id),
            sent_date   DATE NOT NULL,
            sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_daily_send_date ON daily_send_log(sent_date);

        CREATE TABLE IF NOT EXISTS search_queries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text      TEXT NOT NULL,
            region          TEXT DEFAULT 'tr-tr',
            results_count   INTEGER DEFAULT 0,
            executed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            entity_type TEXT DEFAULT '',
            entity_id   INTEGER,
            details     TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Migrate existing databases: add new columns if missing
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(leads)").fetchall()}
    if "decision_maker_linkedin" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN decision_maker_linkedin TEXT DEFAULT ''")
    if "decision_maker_bio" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN decision_maker_bio TEXT DEFAULT ''")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def log_activity(db, action, entity_type="", entity_id=None, details=""):
    db.execute(
        "INSERT INTO activity_log (action, entity_type, entity_id, details) VALUES (?, ?, ?, ?)",
        (action, entity_type, entity_id, details)
    )
    db.commit()


if __name__ == "__main__":
    init_db()
