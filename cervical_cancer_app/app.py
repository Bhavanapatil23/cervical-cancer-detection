from flask import Flask, render_template, request, jsonify
import pickle, pandas as pd, os, csv, sqlite3
from datetime import datetime

app = Flask(__name__)
DB_PATH = "cervical_cancer.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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

def classify_risk(prob):
    if prob >= 0.22: return "High Risk","danger"
    elif prob >= 0.08: return "Medium Risk","warning"
    else: return "Low Risk","success"

def save_to_db(patient_name, input_data, prediction, confidence):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO predictions (
            patient_name, age, sexual_partners, first_intercourse,
            pregnancies, smokes, smokes_years, hormonal_contraceptives,
            iud, stds, stds_number, stds_hpv,
            prediction, confidence, timestamp
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def get_all_predictions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, patient_name, age, sexual_partners, first_intercourse, pregnancies, smokes, smokes_years, hormonal_contraceptives, iud, stds, stds_number, stds_hpv, prediction, confidence, timestamp FROM predictions ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "patient_name": r[1],
            "age": r[2],
            "sexual_partners": r[3],
            "first_intercourse": r[4],
            "pregnancies": r[5],
            "smokes": r[6],
            "smokes_years": r[7],
            "hormonal_contraceptives": r[8],
            "iud": r[9],
            "stds": r[10],
            "stds_number": r[11],
            "stds_hpv": r[12],
            "prediction": r[13],
            "confidence": r[14],
            "timestamp": r[15]
        })
    return result

def get_risk_counts():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT prediction, COUNT(*) FROM predictions GROUP BY prediction")
    rows = cur.fetchall()
    conn.close()
    counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    for pred, cnt in rows:
        if pred in counts:
            counts[pred] = cnt
    return counts

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predict", methods=["POST"])
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
    df = pd.DataFrame([input_data])
    prob = float(model.predict_proba(df)[0][1])
    risk_label, risk_class = classify_risk(prob)
    confidence = f"{prob*100:.1f}%"
    recommendations = get_recommendations(risk_label, input_data)
    testing_recs = get_testing_recommendations(risk_label, input_data)
    try:
        save_to_db(patient_name, input_data, risk_label, confidence)
        print(f"Saved: {patient_name} -> {risk_label}")
    except Exception as e:
        print(f"DB save failed: {e}")
    return render_template("result.html",
        patient_name=patient_name, prediction=risk_label,
        risk_class=risk_class, confidence=confidence,
        prob_at_risk=round(prob*100, 1),
        recommendations=recommendations,
        testing_recs=testing_recs,
        input_data=input_data)

@app.route("/dashboard")
def dashboard():
    history = get_all_predictions()
    risk_counts = get_risk_counts()
    total = len(history)
    return render_template("dashboard.html",
        history=history, risk_counts=risk_counts, total=total)

@app.route("/vaccine")
def vaccine():
    return render_template("vaccine.html")

@app.route("/api/history")
def api_history():
    return jsonify(get_all_predictions())

@app.route("/api/stats")
def api_stats():
    counts = get_risk_counts()
    return jsonify({"counts": counts, "total": sum(counts.values())})

@app.route("/api/delete/<int:record_id>", methods=["DELETE"])
def delete_record(record_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("DELETE FROM predictions WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def get_recommendations(risk_label, data):
    recs = []
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
            {"name":"Pap Smear","priority":"Urgent","frequency":"Immediately, then every 6 months","description":"Detects abnormal cervical cells before they become cancerous.","icon":"🔬"},
            {"name":"Colposcopy","priority":"Urgent","frequency":"As soon as possible","description":"Detailed examination of the cervix using a magnifying instrument.","icon":"🔍"},
            {"name":"HPV DNA Test","priority":"High","frequency":"Immediately","description":"Detects high-risk HPV strains linked to cervical cancer.","icon":"🧬"},
            {"name":"Biopsy","priority":"High","frequency":"If colposcopy shows abnormalities","description":"Tissue sample to check for cancerous or pre-cancerous cells.","icon":"🏥"},
            {"name":"STD Screening Panel","priority":"High","frequency":"Immediately","description":"Full screening for sexually transmitted infections including HIV.","icon":"🩺"},
            {"name":"Pelvic Ultrasound","priority":"Medium","frequency":"As recommended by doctor","description":"Imaging to examine the uterus, ovaries and cervix.","icon":"📡"},
        ]
    elif risk_label == "Medium Risk":
        tests = [
            {"name":"Pap Smear","priority":"High","frequency":"Within 1-3 months, then annually","description":"Detects abnormal cervical cells before they become cancerous.","icon":"🔬"},
            {"name":"HPV DNA Test","priority":"High","frequency":"Within 3 months","description":"Detects high-risk HPV strains linked to cervical cancer.","icon":"🧬"},
            {"name":"STD Screening Panel","priority":"Medium","frequency":"Within 1-3 months","description":"Screening for sexually transmitted infections.","icon":"🩺"},
            {"name":"Pelvic Examination","priority":"Medium","frequency":"Every 6 months","description":"Physical examination of the pelvic region by a gynaecologist.","icon":"👩‍⚕️"},
            {"name":"Colposcopy","priority":"Medium","frequency":"If Pap smear shows abnormalities","description":"Detailed cervical examination if Pap smear results are abnormal.","icon":"🔍"},
        ]
    else:
        tests = [
            {"name":"Pap Smear","priority":"Routine","frequency":"Every 1-3 years","description":"Routine screening to detect any early abnormal cervical cells.","icon":"🔬"},
            {"name":"HPV Vaccination","priority":"Routine","frequency":"If not yet vaccinated","description":"Gardasil / Cervarix vaccine - highly effective against HPV strains.","icon":"💉"},
            {"name":"Pelvic Examination","priority":"Routine","frequency":"Annually","description":"Routine annual gynaecological check-up.","icon":"👩‍⚕️"},
            {"name":"STD Screening","priority":"Routine","frequency":"As recommended based on lifestyle","description":"Basic STD screening as part of annual health check.","icon":"🩺"},
        ]
    if data.get("STDs:HPV", 0) == 1 and risk_label != "High Risk":
        tests.insert(0, {"name":"HPV Genotyping Test","priority":"High","frequency":"Immediately","description":"Identifies the specific HPV strain to assess cancer risk level.","icon":"🧬"})
    return tests

if __name__ == "__main__":
    app.run(debug=True)
