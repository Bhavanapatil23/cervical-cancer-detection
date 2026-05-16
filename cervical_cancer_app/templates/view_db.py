"""
Run anytime to see what's stored in the database:
    python view_db.py
"""

import sqlite3

DB_PATH = "cervical_cancer.db"

def view():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM predictions")
    total = cur.fetchone()[0]

    print("=" * 70)
    print(f"  CervixGuard AI — Database Records ({total} total)")
    print("=" * 70)

    cur.execute("SELECT * FROM predictions ORDER BY id DESC")
    rows = cur.fetchall()

    if not rows:
        print("  No records yet. Submit a form to add data.")
    else:
        for r in rows:
            print(f"\n  ID        : {r['id']}")
            print(f"  Patient   : {r['patient_name']}")
            print(f"  Age       : {r['age']}")
            print(f"  Prediction: {r['prediction']}")
            print(f"  Confidence: {r['confidence']}")
            print(f"  Timestamp : {r['timestamp']}")
            print("  " + "-" * 40)

    # Risk breakdown
    cur.execute("SELECT prediction, COUNT(*) FROM predictions GROUP BY prediction")
    counts = cur.fetchall()
    print("\n  Risk Breakdown:")
    for pred, cnt in counts:
        print(f"    {pred}: {cnt}")

    conn.close()
    print("=" * 70)

if __name__ == "__main__":
    view()