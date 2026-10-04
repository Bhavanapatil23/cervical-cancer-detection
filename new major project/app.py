
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
import pickle, pandas as pd, os, sqlite3, io, re, smtplib, threading, time
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
 
try:
    from dotenv import load_dotenv
    load_dotenv()  # reads a .env file in the project root, if present, into os.environ
except ImportError:
    pass  # python-dotenv not installed — env vars can still be set the normal way
 
from translations import TRANSLATIONS, LANG_NAMES, get_translator
 
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cervixguard-dev-secret-change-me")
DB_PATH = "cervical_cancer.db"
 
# ── Email (for vaccine dose reminders) ──
# Configure via environment variables. If SMTP_HOST is unset, reminder emails
# are printed to the console instead of sent, so the app still runs without mail setup.
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USERNAME or "no-reply@cervixguard.local")
REMINDER_CHECK_INTERVAL_SECONDS = int(os.environ.get("REMINDER_CHECK_INTERVAL_SECONDS", str(24 * 60 * 60)))
 
SYMPTOM_FIELDS = [
    "symptom_bleeding",
    "symptom_postcoital",
    "symptom_discharge",
    "symptom_pelvic_pain",
    "symptom_pain_intercourse",
]
SYMPTOM_LABELS = {
    "symptom_bleeding": "Abnormal bleeding",
    "symptom_postcoital": "Post-intercourse bleeding",
    "symptom_discharge": "Unusual discharge",
    "symptom_pelvic_pain": "Pelvic pain",
    "symptom_pain_intercourse": "Pain during intercourse",
}
 
FOLLOWUP_DAYS = {"High Risk": 7, "Medium Risk": 30, "Low Risk": 365}
 
 
# ─────────────────────────── Database ───────────────────────────
 
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
 
 
def init_db():
    conn = get_conn()
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            age REAL, sexual_partners REAL, first_intercourse REAL,
            pregnancies REAL, smokes REAL, smokes_years REAL,
            hormonal_contraceptives REAL, iud REAL, stds REAL,
            stds_number REAL, stds_hpv REAL,
            prediction TEXT, confidence TEXT, timestamp TEXT
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
 
    # Migrate: add any columns that predate this version.
    cur.execute("PRAGMA table_info(predictions)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col in SYMPTOM_FIELDS + ["urgent_flag", "user_id"]:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE predictions ADD COLUMN {col} INTEGER DEFAULT 0")
 
    cur.execute("PRAGMA table_info(users)")
    existing_user_cols = {row[1] for row in cur.fetchall()}
    if "email" not in existing_user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
 
    cur.execute("PRAGMA table_info(vaccine_registrations)")
    existing_vax_cols = {row[1] for row in cur.fetchall()}
    for col in ["dose1_reminder_sent", "dose2_reminder_sent", "dose3_reminder_sent"]:
        if col not in existing_vax_cols:
            cur.execute(f"ALTER TABLE vaccine_registrations ADD COLUMN {col} INTEGER DEFAULT 0")
 
    conn.commit()
    conn.close()
    print("Database ready:", DB_PATH)
 
 
init_db()
 
MODEL_PATH = "model.pkl"
model_data = None
 
 
def load_model():
    global model_data
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            model_data = pickle.load(f)
        print("Model loaded.")
    else:
        print("model.pkl not found. Run train_model.py first.")
 
 
load_model()
 
 
# ─────────────────────────── Auth helpers ───────────────────────────
 
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped
 
 
@app.context_processor
def inject_globals():
    lang = session.get("lang", "en")
    return {
        "t": get_translator(lang),
        "current_lang": lang,
        "lang_names": LANG_NAMES,
        "current_user": session.get("username"),
    }
 
 
@app.route("/lang/<code>")
def set_lang(code):
    if code in TRANSLATIONS:
        session["lang"] = code
    return redirect(request.referrer or url_for("index"))
 
 
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip() or None
        if not username or not password:
            flash("Username and password are required.")
            return render_template("register.html")
        if len(password) < 4:
            flash("Password must be at least 4 characters.")
            return render_template("register.html")
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            conn.close()
            flash("That username is already taken.")
            return render_template("register.html")
        cur.execute(
            "INSERT INTO users (username, password_hash, email, created_at) VALUES (?,?,?,?)",
            (username, generate_password_hash(password), email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        session["user_id"] = user_id
        session["username"] = username
        return redirect(url_for("index"))
    return render_template("register.html")
 
 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash("Invalid username or password.")
    return render_template("login.html")
 
 
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
 
 
# ─────────────────────────── Core prediction ───────────────────────────
 
def classify_risk(prob):
    if prob >= 0.22:
        return "High Risk", "danger"
    elif prob >= 0.08:
        return "Medium Risk", "warning"
    else:
        return "Low Risk", "success"
 
 
def save_to_db(user_id, patient_name, input_data, symptoms, urgent_flag, prediction, confidence):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO predictions (
            patient_name, age, sexual_partners, first_intercourse,
            pregnancies, smokes, smokes_years, hormonal_contraceptives,
            iud, stds, stds_number, stds_hpv,
            prediction, confidence, timestamp,
            symptom_bleeding, symptom_postcoital, symptom_discharge,
            symptom_pelvic_pain, symptom_pain_intercourse, urgent_flag, user_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        patient_name,
        input_data.get("Age", 0),
        input_data.get("Number of sexual partners", 0),
        input_data.get("First sexual intercourse", 0),
        input_data.get("Num of pregnancies", 0),
        input_data.get("Smokes", 0),
        input_data.get("Smokes (years)", 0),
        input_data.get("Hormonal Contraceptives", 0),
        input_data.get("IUD", 0),
        input_data.get("STDs", 0),
        input_data.get("STDs (number)", 0),
        input_data.get("STDs:HPV", 0),
        prediction, confidence,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        symptoms.get("symptom_bleeding", 0),
        symptoms.get("symptom_postcoital", 0),
        symptoms.get("symptom_discharge", 0),
        symptoms.get("symptom_pelvic_pain", 0),
        symptoms.get("symptom_pain_intercourse", 0),
        int(urgent_flag),
        user_id,
    ))
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id
 
 
def get_record(record_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE id = ? AND user_id = ?", (record_id, user_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None
 
 
def get_all_predictions(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM predictions WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "patient_name": r["patient_name"],
            "age": r["age"],
            "sexual_partners": r["sexual_partners"],
            "first_intercourse": r["first_intercourse"],
            "pregnancies": r["pregnancies"],
            "smokes": r["smokes"],
            "smokes_years": r["smokes_years"],
            "hormonal_contraceptives": r["hormonal_contraceptives"],
            "iud": r["iud"],
            "stds": r["stds"],
            "stds_number": r["stds_number"],
            "stds_hpv": r["stds_hpv"],
            "prediction": r["prediction"],
            "confidence": r["confidence"],
            "timestamp": r["timestamp"],
            "urgent_flag": r.get("urgent_flag", 0),
        })
    return result
 
 
def get_risk_counts(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT prediction, COUNT(*) FROM predictions WHERE user_id = ? GROUP BY prediction", (user_id,))
    rows = cur.fetchall()
    conn.close()
    counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for pred, cnt in rows:
        if pred in counts:
            counts[pred] = cnt
    return counts
 
 
@app.route("/")
@login_required
def index():
    return render_template("index.html", active="assess")
 
 
@app.route("/predict", methods=["POST"])
@login_required
def predict():
    if model_data is None:
        return render_template("result.html", error="Model not loaded. Run train_model.py first.")
    model = model_data["model"]
    features = model_data["features"]
    patient_name = request.form.get("patient_name", "").strip() or "Unknown"
 
    try:
        input_data = {feat: float(request.form.get(feat, 0)) for feat in features}
    except Exception as e:
        return render_template("result.html", error=str(e))
 
    symptoms = {f: int(request.form.get(f, 0) == "1") for f in SYMPTOM_FIELDS}
    urgent_flag = any(symptoms.values())
 
    df = pd.DataFrame([input_data])
    prob = float(model.predict_proba(df)[0][1])
    risk_label, risk_class = classify_risk(prob)
    confidence = f"{prob * 100:.1f}%"
 
    recommendations = get_recommendations(risk_label, input_data, symptoms)
    testing_recs = get_testing_recommendations(risk_label, input_data)
 
    record_id = None
    try:
        record_id = save_to_db(session["user_id"], patient_name, input_data, symptoms,
                                urgent_flag, risk_label, confidence)
        print(f"Saved: {patient_name} -> {risk_label} (id={record_id})")
    except Exception as e:
        print(f"DB save failed: {e}")
 
    # Remember the latest result for the chatbot's context.
    session["last_result"] = {
        "patient_name": patient_name,
        "risk": risk_label,
        "confidence": confidence,
        "urgent": urgent_flag,
    }
 
    suggested_days = FOLLOWUP_DAYS.get(risk_label, 180)
    suggested_date = (datetime.now() + timedelta(days=suggested_days)).strftime("%Y-%m-%d")
 
    input_data_display = dict(input_data)
    input_data_display.update(symptoms)
 
    return render_template(
        "result.html",
        patient_name=patient_name, prediction=risk_label,
        risk_class=risk_class, confidence=confidence,
        prob_at_risk=round(prob * 100, 1),
        recommendations=recommendations,
        testing_recs=testing_recs,
        input_data=input_data_display,
        record_id=record_id,
        suggested_date=suggested_date,
    )
 
 
@app.route("/dashboard")
@login_required
def dashboard():
    history = get_all_predictions(session["user_id"])
    risk_counts = get_risk_counts(session["user_id"])
    total = len(history)
 
    # Cumulative assessments-over-time series for the dashboard trend chart.
    by_date = {}
    for r in sorted(history, key=lambda r: r["timestamp"]):
        d = r["timestamp"][:10]
        by_date[d] = by_date.get(d, 0) + 1
    running = 0
    trend_points = []
    for d in sorted(by_date):
        running += by_date[d]
        trend_points.append({"date": d, "value": running})
 
    return render_template("dashboard.html", active="dashboard",
                            history=history, risk_counts=risk_counts, total=total,
                            trend_points=trend_points)
 
 
@app.route("/vaccine")
def vaccine():
    registrations = []
    if session.get("user_id"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM vaccine_registrations WHERE user_id = ? ORDER BY dose1_date ASC",
            (session["user_id"],),
        )
        registrations = [dict(r) for r in cur.fetchall()]
        conn.close()
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("vaccine.html", active="vaccine", registrations=registrations, today=today)
 
 
@app.route("/api/history")
@login_required
def api_history():
    return jsonify(get_all_predictions(session["user_id"]))
 
 
@app.route("/api/stats")
@login_required
def api_stats():
    counts = get_risk_counts(session["user_id"])
    return jsonify({"counts": counts, "total": sum(counts.values())})
 
 
@app.route("/api/delete/<int:record_id>", methods=["DELETE"])
@login_required
def delete_record(record_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM predictions WHERE id = ? AND user_id = ?", (record_id, session["user_id"]))
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return jsonify({"success": bool(deleted)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
 
 
@app.route("/report/<int:record_id>")
@login_required
def download_report(record_id):
    record = get_record(record_id, session["user_id"])
    if not record:
        return "Report not found.", 404
 
    input_data = {
        "Age": record["age"],
        "Number of sexual partners": record["sexual_partners"],
        "First sexual intercourse": record["first_intercourse"],
        "Num of pregnancies": record["pregnancies"],
        "Smokes": record["smokes"],
        "Smokes (years)": record["smokes_years"],
        "Hormonal Contraceptives": record["hormonal_contraceptives"],
        "IUD": record["iud"],
        "STDs": record["stds"],
        "STDs (number)": record["stds_number"],
        "STDs:HPV": record["stds_hpv"],
    }
    symptoms = {f: record.get(f, 0) for f in SYMPTOM_FIELDS}
    recommendations = get_recommendations(record["prediction"], input_data, symptoms)
    testing_recs = get_testing_recommendations(record["prediction"], input_data)
 
    pdf_bytes = build_pdf_report(record, input_data, symptoms, recommendations, testing_recs)
    filename = f"CervixGuard_Report_{record['patient_name'].replace(' ', '_')}_{record['id']}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
 
 
def build_pdf_report(record, input_data, symptoms, recommendations, testing_recs):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
 
    TEAL = colors.HexColor("#0E7C86")
    VIOLET = colors.HexColor("#7C3AED")
    RISK_COLORS = {
        "High Risk": colors.HexColor("#E24C4C"),
        "Medium Risk": colors.HexColor("#DB9200"),
        "Low Risk": colors.HexColor("#12A870"),
    }
    risk_color = RISK_COLORS.get(record["prediction"], TEAL)
 
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=26 * mm, bottomMargin=20 * mm,
                             leftMargin=20 * mm, rightMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=TEAL, fontSize=20, spaceAfter=2)
    sub_style = ParagraphStyle("SubX", parent=styles["Normal"], textColor=colors.HexColor("#5B6E70"), fontSize=10)
    h2 = ParagraphStyle("H2X", parent=styles["Heading2"], textColor=VIOLET, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=10, leading=14)
    risk_style = ParagraphStyle("RiskX", parent=styles["Heading1"], textColor=risk_color,
                                 alignment=TA_CENTER, fontSize=22, spaceBefore=6, spaceAfter=2)
 
    story = []
    story.append(Paragraph("CervixGuard AI", title_style))
    story.append(Paragraph("Cervical Cancer Risk Assessment Report", sub_style))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#DCEAE8"), spaceBefore=8, spaceAfter=12))
 
    story.append(Paragraph(f"Patient: <b>{record['patient_name']}</b>", body))
    story.append(Paragraph(f"Generated: {record['timestamp']}", body))
    story.append(Spacer(1, 10))
 
    story.append(Paragraph(record["prediction"], risk_style))
    story.append(Paragraph(f"Model estimate — probability at risk: <b>{record['confidence']}</b>",
                            ParagraphStyle("ConfX", parent=body, alignment=TA_CENTER)))
    story.append(Spacer(1, 6))
 
    if any(symptoms.values()):
        flagged = [SYMPTOM_LABELS[k] for k, v in symptoms.items() if v]
        story.append(Paragraph(
            "⚠ Symptom alert: " + ", ".join(flagged) +
            " — clinical evaluation is advised regardless of the risk tier above.",
            ParagraphStyle("AlertX", parent=body, textColor=colors.HexColor("#E24C4C"),
                            borderColor=colors.HexColor("#E24C4C"), borderWidth=0.5,
                            borderPadding=6, backColor=colors.HexColor("#FBE7E7"))
        ))
 
    story.append(Paragraph("Health factors provided", h2))
    factor_rows = [["Factor", "Value"]]
    for k, v in input_data.items():
        factor_rows.append([k, str(int(v)) if float(v).is_integer() else str(v)])
    t = Table(factor_rows, colWidths=[110 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCEAE8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F8F6")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
 
    story.append(Paragraph("Recommendations", h2))
    for r in recommendations:
        story.append(Paragraph(f"• {r}", body))
 
    story.append(Paragraph("Suggested tests", h2))
    test_rows = [["Test", "Priority", "Frequency"]]
    for tst in testing_recs:
        test_rows.append([tst["name"], tst["priority"], tst["frequency"]])
    t2 = Table(test_rows, colWidths=[60 * mm, 30 * mm, 70 * mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VIOLET),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DCEAE8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F8F6")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)
 
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#DCEAE8")))
    story.append(Paragraph(
        "This report is generated by an educational decision-support tool and is not a medical "
        "diagnosis. Always consult a licensed healthcare professional.",
        ParagraphStyle("FootX", parent=body, fontSize=8, textColor=colors.HexColor("#8AA0A0"), spaceBefore=8)
    ))
 
    doc.build(story)
    return buf.getvalue()
 
 
def get_recommendations(risk_label, data, symptoms=None):
    symptoms = symptoms or {}
    recs = []
    if any(symptoms.values()):
        recs.append("You reported symptoms that warrant a clinical evaluation regardless of risk tier — please book a gynaecologist visit soon.")
    if risk_label == "High Risk":
        recs += ["Immediate consultation with a gynaecologist is strongly advised.",
                 "Schedule a Pap smear and colposcopy at the earliest.",
                 "Do not delay - early diagnosis significantly improves outcomes."]
    elif risk_label == "Medium Risk":
        recs += ["Consult a gynaecologist within the next few weeks.",
                 "A Pap smear test is recommended soon.",
                 "Schedule a follow-up within 3-6 months."]
    else:
        recs += ["Continue regular annual gynaecological check-ups.",
                 "Next Pap smear recommended within 1-3 years as per guidelines."]
    if data.get("Smokes", 0) == 1: recs.append("Quit smoking - it significantly increases cervical cancer risk.")
    if data.get("STDs:HPV", 0) == 1: recs.append("HPV vaccination and regular monitoring are very important.")
    if data.get("Hormonal Contraceptives", 0) == 1: recs.append("Discuss long-term contraceptive use with your doctor.")
    if data.get("IUD", 0) == 1: recs.append("Periodic IUD check-ups are recommended.")
    recs.append("This tool is for educational purposes and not a substitute for medical advice.")
    return recs
 
 
def get_testing_recommendations(risk_label, data):
    if risk_label == "High Risk":
        tests = [
            {"name": "Pap Smear", "priority": "Urgent", "frequency": "Immediately, then every 6 months", "description": "Detects abnormal cervical cells before they become cancerous.", "icon": "🔬"},
            {"name": "Colposcopy", "priority": "Urgent", "frequency": "As soon as possible", "description": "Detailed examination of the cervix using a magnifying instrument.", "icon": "🔍"},
            {"name": "HPV DNA Test", "priority": "High", "frequency": "Immediately", "description": "Detects high-risk HPV strains linked to cervical cancer.", "icon": "🧬"},
            {"name": "Biopsy", "priority": "High", "frequency": "If colposcopy shows abnormalities", "description": "Tissue sample to check for cancerous or pre-cancerous cells.", "icon": "🏥"},
            {"name": "STD Screening Panel", "priority": "High", "frequency": "Immediately", "description": "Full screening for sexually transmitted infections including HIV.", "icon": "🩺"},
            {"name": "Pelvic Ultrasound", "priority": "Medium", "frequency": "As recommended by doctor", "description": "Imaging to examine the uterus, ovaries and cervix.", "icon": "📡"},
        ]
    elif risk_label == "Medium Risk":
        tests = [
            {"name": "Pap Smear", "priority": "High", "frequency": "Within 1-3 months, then annually", "description": "Detects abnormal cervical cells before they become cancerous.", "icon": "🔬"},
            {"name": "HPV DNA Test", "priority": "High", "frequency": "Within 3 months", "description": "Detects high-risk HPV strains linked to cervical cancer.", "icon": "🧬"},
            {"name": "STD Screening Panel", "priority": "Medium", "frequency": "Within 1-3 months", "description": "Screening for sexually transmitted infections.", "icon": "🩺"},
            {"name": "Pelvic Examination", "priority": "Medium", "frequency": "Every 6 months", "description": "Physical examination of the pelvic region by a gynaecologist.", "icon": "👩‍⚕️"},
            {"name": "Colposcopy", "priority": "Medium", "frequency": "If Pap smear shows abnormalities", "description": "Detailed cervical examination if Pap smear results are abnormal.", "icon": "🔍"},
        ]
    else:
        tests = [
            {"name": "Pap Smear", "priority": "Routine", "frequency": "Every 1-3 years", "description": "Routine screening to detect any early abnormal cervical cells.", "icon": "🔬"},
            {"name": "HPV Vaccination", "priority": "Routine", "frequency": "If not yet vaccinated", "description": "Gardasil / Cervarix vaccine - highly effective against HPV strains.", "icon": "💉"},
            {"name": "Pelvic Examination", "priority": "Routine", "frequency": "Annually", "description": "Routine annual gynaecological check-up.", "icon": "👩‍⚕️"},
            {"name": "STD Screening", "priority": "Routine", "frequency": "As recommended based on lifestyle", "description": "Basic STD screening as part of annual health check.", "icon": "🩺"},
        ]
    if data.get("STDs:HPV", 0) == 1 and risk_label != "High Risk":
        tests.insert(0, {"name": "HPV Genotyping Test", "priority": "High", "frequency": "Immediately", "description": "Identifies the specific HPV strain to assess cancer risk level.", "icon": "🧬"})
    return tests
 
 
# ─────────────────────────── Vaccine registration & reminders ───────────────────────────
 
def compute_dose_schedule(age, dose1_date_str):
    """Given age and the date of dose 1, compute how many doses are needed and
    the recommended dates for the remaining doses, per standard HPV guidance."""
    dose1 = datetime.strptime(dose1_date_str, "%Y-%m-%d")
    if age < 15:
        doses_required = 2
        dose2 = dose1 + timedelta(days=182)  # ~6 months
        dose3 = None
    else:
        doses_required = 3
        dose2 = dose1 + timedelta(days=30)   # ~1 month
        dose3 = dose1 + timedelta(days=182)  # ~6 months
    return {
        "doses_required": doses_required,
        "dose1_date": dose1.strftime("%Y-%m-%d"),
        "dose2_date": dose2.strftime("%Y-%m-%d"),
        "dose3_date": dose3.strftime("%Y-%m-%d") if dose3 else None,
    }
 
 
@app.route("/vaccine/register", methods=["POST"])
@login_required
def register_vaccine():
    patient_name = request.form.get("patient_name", "").strip() or "Unknown"
    try:
        age = float(request.form.get("age", 0))
    except ValueError:
        age = 0
    dose1_date_str = request.form.get("start_date") or datetime.now().strftime("%Y-%m-%d")
 
    schedule = compute_dose_schedule(age, dose1_date_str)
 
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vaccine_registrations
            (user_id, patient_name, age, doses_required, dose1_date, dose2_date, dose3_date, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        session["user_id"], patient_name, age, schedule["doses_required"],
        schedule["dose1_date"], schedule["dose2_date"], schedule["dose3_date"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("vaccine"))
 
 
@app.route("/vaccine/dose/<int:reg_id>/<int:dose_num>/done", methods=["POST"])
@login_required
def mark_dose_done(reg_id, dose_num):
    if dose_num not in (1, 2, 3):
        return redirect(url_for("vaccine"))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE vaccine_registrations SET dose{dose_num}_done = 1 WHERE id = ? AND user_id = ?",
        (reg_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return redirect(url_for("vaccine"))
 
 
@app.route("/vaccine/registration/<int:reg_id>/delete", methods=["POST"])
@login_required
def delete_vaccine_registration(reg_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM vaccine_registrations WHERE id = ? AND user_id = ?", (reg_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("vaccine"))
 
 
@app.route("/vaccine/dose/<int:reg_id>/<int:dose_num>/ics")
@login_required
def dose_ics(reg_id, dose_num):
    if dose_num not in (1, 2, 3):
        return "Invalid dose.", 404
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM vaccine_registrations WHERE id = ? AND user_id = ?", (reg_id, session["user_id"]))
    reg = cur.fetchone()
    conn.close()
    if not reg:
        return "Registration not found.", 404
 
    date_field = f"dose{dose_num}_date"
    dose_date = reg[date_field]
    if not dose_date:
        return "This dose isn't scheduled for this plan.", 404
 
    date_str = dose_date.replace("-", "")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CervixGuard AI//Vaccine//EN",
        "BEGIN:VEVENT",
        f"UID:cervixguard-vax-{reg['id']}-dose{dose_num}@local",
        f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{date_str}",
        f"SUMMARY:CervixGuard AI — HPV Vaccine Dose {dose_num} ({reg['patient_name']})",
        "DESCRIPTION:HPV vaccination reminder generated by CervixGuard AI.",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])
    return send_file(
        io.BytesIO(ics.encode("utf-8")),
        mimetype="text/calendar",
        as_attachment=True,
        download_name=f"hpv_dose{dose_num}_{reg['id']}.ics",
    )
 
 
# ─────────────────────────── Vaccine reminder emails ───────────────────────────
 
def send_email(to_addr, subject, body):
    """Send a plain-text email. Falls back to logging to the console if SMTP
    isn't configured, so the app works out of the box without mail setup."""
    if not to_addr:
        return False
    if not SMTP_HOST:
        print(f"[reminder email — SMTP not configured, printing instead]\nTo: {to_addr}\nSubject: {subject}\n{body}\n")
        return True
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = to_addr
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, [to_addr], msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send reminder email to {to_addr}: {e}")
        return False
 
 
def check_and_send_vaccine_reminders():
    """Find HPV vaccine doses whose due date has arrived (today or earlier),
    aren't marked done yet, and haven't already had a reminder sent — email
    the account holder for each, then mark it sent so it isn't repeated."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.*, u.email AS user_email
        FROM vaccine_registrations v
        JOIN users u ON u.id = v.user_id
        WHERE u.email IS NOT NULL AND u.email != ''
    """)
    regs = [dict(r) for r in cur.fetchall()]
 
    sent_count = 0
    for reg in regs:
        for dose_num in range(1, reg["doses_required"] + 1):
            date_field = f"dose{dose_num}_date"
            done_field = f"dose{dose_num}_done"
            sent_field = f"dose{dose_num}_reminder_sent"
            dose_date = reg.get(date_field)
            if not dose_date or reg.get(done_field) or reg.get(sent_field):
                continue
            if dose_date > today:
                continue  # not due yet
 
            subject = f"CervixGuard AI — HPV vaccine dose {dose_num} is due"
            body = (
                f"Hi,\n\nThis is a reminder that HPV vaccine dose {dose_num} for "
                f"{reg['patient_name']} was due on {dose_date}.\n\n"
                "Please book it with your clinic soon if it hasn't been given yet. "
                "You can mark it as done from the Vaccine page once it's administered.\n\n"
                "— CervixGuard AI (educational tool, not a diagnosis)"
            )
            if send_email(reg["user_email"], subject, body):
                cur.execute(
                    f"UPDATE vaccine_registrations SET {sent_field} = 1 WHERE id = ?",
                    (reg["id"],),
                )
                sent_count += 1
    conn.commit()
    conn.close()
    if sent_count:
        print(f"Sent {sent_count} vaccine dose reminder email(s).")
    return sent_count
 
 
def _reminder_loop():
    while True:
        try:
            check_and_send_vaccine_reminders()
        except Exception as e:
            print(f"Vaccine reminder check failed: {e}")
        time.sleep(REMINDER_CHECK_INTERVAL_SECONDS)
 
 
def start_reminder_scheduler():
    # Avoid double-starting the background thread under the Flask debug reloader,
    # which re-executes this module in a child process with WERKZEUG_RUN_MAIN=true.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        thread = threading.Thread(target=_reminder_loop, daemon=True)
        thread.start()
 
 
# ─────────────────────────── Chatbot (rule-based, fully local) ───────────────────────────
 
CHAT_RULES = [
    (r"\b(hi|hello|hey|namaste)\b", "Hi! I'm the CervixGuard assistant. Ask me about your risk result, Pap smears, HPV, the vaccine, or what to do next."),
    (r"\b(risk tier|what does my (result|risk) mean|what does .*(low|medium|high) risk mean)\b",
     "context_risk"),
    (r"\b(pap smear|pap test)\b",
     "A Pap smear checks cervical cells for early abnormal changes, years before they could become cancer. It's quick, done in a clinic, and the single most effective cervical cancer screening tool we have."),
    (r"\bhpv\b.*\b(test|dna)\b",
     "An HPV DNA test checks for the high-risk HPV strains that cause most cervical cancers. It's often done alongside or instead of a Pap smear, depending on your age and guidelines."),
    (r"\b(hpv)\b",
     "HPV (human papillomavirus) is a very common virus; most infections clear on their own, but persistent high-risk strains can lead to cervical cancer over time. Vaccination and regular screening are the best defenses."),
    (r"\b(vaccine|vaccination|gardasil|cervarix)\b",
     "The HPV vaccine protects against the strains responsible for most cervical cancers. It's most effective before HPV exposure, but catch-up doses are available up to age 45 — check the Vaccine page for the full dosing schedule."),
    (r"\b(colposcopy)\b",
     "A colposcopy is a closer, magnified examination of the cervix, usually done as a follow-up when a Pap smear shows abnormal cells."),
    (r"\b(biopsy)\b",
     "A biopsy takes a small tissue sample from the cervix to check under a microscope for pre-cancerous or cancerous cells — usually done if a colposcopy shows something abnormal."),
    (r"\b(symptom|bleeding|discharge|pelvic pain|pain during sex|pain during intercourse)\b",
     "Symptoms like abnormal bleeding, unusual discharge, or pelvic pain are worth a clinical evaluation regardless of any risk score — they aren't something a model like this one can safely rule out."),
    (r"\b(next step|what should i do|what now|what next)\b", "context_next"),
    (r"\b(appointment|book|schedule|follow.?up)\b",
     "It's worth booking a follow-up with a clinician — your result page shows a suggested timeframe based on your risk tier."),
    (r"\b(accurate|reliable|trust|how good is)\b.*\b(model|prediction|this)\b",
     "This model was trained on a public clinical dataset and reaches roughly 95% accuracy in testing, but it's a screening aid, not a diagnosis — always confirm results with a real clinician."),
    (r"\b(thank|thanks|thank you)\b", "You're welcome! Take care of yourself, and don't hesitate to see a doctor if anything feels off."),
    (r"\b(bye|goodbye)\b", "Take care! Your assessments are always saved on your Dashboard if you want to revisit them."),
]
 
FALLBACK_REPLY = ("I'm a simple local assistant, so I can only help with cervical health topics — "
                   "try asking about your risk result, Pap smears, HPV, the vaccine, symptoms, or next steps.")
 
 
def chatbot_reply(message, last_result):
    msg = message.lower().strip()
    for pattern, reply in CHAT_RULES:
        if re.search(pattern, msg):
            if reply == "context_risk":
                if last_result:
                    risk = last_result.get("risk", "your last")
                    conf = last_result.get("confidence", "")
                    return (f"Your most recent result was **{risk}** with a model confidence of {conf}. "
                            "That's a statistical estimate from 11 health factors, not a diagnosis — "
                            "check the Recommendations and Suggested Tests on your result page for what to do next.")
                return ("I don't see a recent assessment for you yet — run one from the Assess page and I can "
                        "explain exactly what your risk tier means.")
            if reply == "context_next":
                if last_result and last_result.get("urgent"):
                    return "You reported symptoms on your last assessment — please prioritize a clinical evaluation soon, regardless of your risk tier."
                if last_result:
                    risk = last_result.get("risk")
                    days = FOLLOWUP_DAYS.get(risk, 180)
                    return f"Based on your last result ({risk}), a follow-up within about {days} days is a reasonable target — worth booking with your clinic."
                return "Start with an assessment on the Assess page — I can help interpret your result once you have one."
            return reply
    return FALLBACK_REPLY
 
 
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not message.strip():
        return jsonify({"reply": "Ask me anything about your result, Pap smears, HPV, the vaccine, or next steps."})
    last_result = session.get("last_result")
    reply = chatbot_reply(message, last_result)
    return jsonify({"reply": reply})
 
 
if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "true").lower() != "false"
    app.debug = debug_mode
    start_reminder_scheduler()
    app.run(debug=debug_mode)
 
