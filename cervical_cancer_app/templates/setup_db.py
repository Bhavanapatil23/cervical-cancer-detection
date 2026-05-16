"""
Run this ONCE before starting the app:
    python setup_db.py

This script:
  1. Creates cervical_cancer.db
  2. Creates the predictions table
  3. Verifies the connection
  4. Shows current record count
"""

import sqlite3
from datetime import datetime

DB_PATH = "cervical_cancer.db"

def setup():
    print("=" * 50)
    print("  CervixGuard AI — Database Setup")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Create predictions table
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

    # Verify
    cur.execute("SELECT COUNT(*) FROM predictions")
    count = cur.fetchone()[0]

    conn.close()

    print(f"\n✅ Database created : {DB_PATH}")
    print(f"✅ Table ready      : predictions")
    print(f"📊 Records stored   : {count}")
    print("\n🚀 You can now run: python app.py")
    print("=" * 50)

if __name__ == "__main__":
    setup()