import sqlite3

DB_PATH = "cervical_cancer.db"

def setup():
    print("=" * 50)
    print("  CervixGuard AI - Database Setup")
    print("=" * 50)
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
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
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM predictions")
    count = cur.fetchone()[0]
    conn.close()
    print(f"✅ Database created : {DB_PATH}")
    print(f"✅ Table ready      : predictions")
    print(f"📊 Records stored   : {count}")
    print("🚀 You can now run: python app.py")
    print("=" * 50)

if __name__ == "__main__":
    setup()
