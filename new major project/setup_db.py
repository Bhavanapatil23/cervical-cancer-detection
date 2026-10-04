
import sqlite3
 
DB_PATH = "cervical_cancer.db"
 
EXTRA_PREDICTION_COLUMNS = [
    "symptom_bleeding", "symptom_postcoital", "symptom_discharge",
    "symptom_pelvic_pain", "symptom_pain_intercourse", "urgent_flag", "user_id",
]
 
EXTRA_VACCINE_COLUMNS = [
    "dose1_reminder_sent", "dose2_reminder_sent", "dose3_reminder_sent",
]
 
 
def setup():
    print("=" * 50)
    print("  CervixGuard AI - Database Setup")
    print("=" * 50)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TEXT
        )
    """)
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name            TEXT    NOT NULL,
            age                     REAL,
            sexual_partners         REAL,
            first_intercourse       REAL,
            pregnancies             REAL,
            smokes                  REAL,
            smokes_years            REAL,
            hormonal_contraceptives REAL,
            iud                     REAL,
            stds                    REAL,
            stds_number             REAL,
            stds_hpv                REAL,
            prediction              TEXT,
            confidence              TEXT,
            timestamp               TEXT
        )
    """)
 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vaccine_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            patient_name TEXT,
            age REAL,
            doses_required INTEGER,
            dose1_date TEXT,
            dose2_date TEXT,
            dose3_date TEXT,
            dose1_done INTEGER DEFAULT 0,
            dose2_done INTEGER DEFAULT 0,
            dose3_done INTEGER DEFAULT 0,
            dose1_reminder_sent INTEGER DEFAULT 0,
            dose2_reminder_sent INTEGER DEFAULT 0,
            dose3_reminder_sent INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
 
    cur.execute("PRAGMA table_info(predictions)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col in EXTRA_PREDICTION_COLUMNS:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE predictions ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"  + added column: predictions.{col}")
 
    cur.execute("PRAGMA table_info(users)")
    existing_user_cols = {row[1] for row in cur.fetchall()}
    if "email" not in existing_user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
        print("  + added column: users.email")
 
    cur.execute("PRAGMA table_info(vaccine_registrations)")
    existing_vax_cols = {row[1] for row in cur.fetchall()}
    for col in EXTRA_VACCINE_COLUMNS:
        if col not in existing_vax_cols:
            cur.execute(f"ALTER TABLE vaccine_registrations ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"  + added column: vaccine_registrations.{col}")
 
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM predictions")
    pred_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    conn.close()
    print(f"Database ready    : {DB_PATH}")
    print(f"Tables ready       : users, predictions, vaccine_registrations")
    print(f"Users registered   : {user_count}")
    print(f"Predictions stored : {pred_count}")
    print("You can now run: python app.py")
    print("=" * 50)
 
 
if __name__ == "__main__":
    setup()
 
