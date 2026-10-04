

Readme · MD
🎗️ CervixGuard AI — Cervical Cancer Risk Assessment System
BCS685 | Acharya Institute of Technology | Dept. of CSE

✨ What's new in this version
Redesigned UI — soft teal/violet "awareness ribbon" theme, rounded cards, a signature animated risk-ring gauge, custom Sora/Inter/JetBrains Mono type system.
Dark mode — toggle in the top nav, persisted per-browser.
Symptom checklist — an optional section on the assessment form (abnormal bleeding, pelvic pain, etc.). It doesn't feed the ML model, but triggers a visible urgency alert and adjusted recommendations, since these symptoms warrant a clinical visit regardless of model score.
PDF report download — every assessment gets a formatted, downloadable PDF (via ReportLab) from the result page or the dashboard history table.
Email & print-friendly result page — "Email summary" opens a pre-filled email draft; "Print" uses a dedicated print stylesheet.
Dashboard analytics — stat cards, a risk-distribution donut chart and an assessments-over-time line chart (Chart.js), plus searchable/filterable history with per-row PDF download and delete.
Vaccine dose reminder emails — if your account has an email on file, you get an automatic email when an HPV dose becomes due (see below).
Appointments removed — the standalone Appointments page/feature has been taken out.
Fixed: the password input on login/register wasn't picking up the form styling (missing CSS selector) — now matches the rest of the fields.
📁 Project Structure
cervical_cancer_app/
├── app.py                  ← Flask backend (main server)
├── train_model.py          ← Train ML model (run first!)
├── evaluate.py              ← Model evaluation + plots
├── setup_db.py              ← Create/migrate the SQLite database
├── view_db.py                ← Quick CLI view of stored records
├── requirements.txt        ← Python dependencies
├── kag_risk_factors_cervical_cancer.csv  ← Training dataset
├── model.pkl                 ← Saved model (regenerate with train_model.py)
├── cervical_cancer.db        ← SQLite database (created on first run)
├── templates/
│   ├── base.html            ← Shared layout, nav, dark-mode toggle
│   ├── index.html           ← Assessment form (incl. symptom checklist)
│   ├── result.html          ← Risk ring, recommendations, PDF/email/print actions
│   ├── dashboard.html       ← Analytics dashboard + history table
│   └── vaccine.html         ← HPV vaccine dosing timeline
└── static/
    ├── css/style.css        ← Design system (light + dark themes, print styles)
    └── js/main.js           ← Theme toggle, form progress, charts, delete/email actions
🚀 How to Run
Step 1 — Install dependencies
bash
pip install -r requirements.txt
Step 2 — Set up the database
bash
python setup_db.py
This creates cervical_cancer.db (SQLite — no external database server needed). app.py also auto-migrates the schema on startup, so re-running an older DB is safe.

Step 3 — Place the dataset (if not already present)
kag_risk_factors_cervical_cancer.csv should sit in the project root. Download from: https://www.kaggle.com/datasets/loveall/cervical-cancer-risk-classification

Step 4 — Train the model
bash
python train_model.py
This generates model.pkl. (A pre-trained one is already included.)

Step 5 — Run the Flask app
bash
python app.py
Open: http://localhost:5000

Step 6 — (Optional) Evaluate the model
bash
python evaluate.py
Generates evaluation_report.png with confusion matrix, ROC curve, and feature importances.

Step 7 — (Optional) Inspect the database from the CLI
bash
python view_db.py
🧠 ML Model Details
Property	Value
Algorithm	Random Forest
Classes	Low / Medium / High (thresholded on predicted probability)
Features	11 health risk factors
Class Imbalance	SMOTE oversampling
Accuracy	~95%
Features Used
Age
Number of sexual partners
Age at first sexual intercourse
Number of pregnancies
Smoking status + years
Hormonal contraceptives
IUD usage
STDs count + HPV diagnosis
Symptom checklist (advisory only, not model inputs)
Abnormal bleeding · Post-intercourse bleeding · Unusual discharge · Pelvic pain · Pain during intercourse
🌐 Pages
Route	Description
/	Risk assessment form
/predict	POST — runs prediction, saves to DB
/dashboard	Analytics with charts + history table
/vaccine	HPV vaccine dosing timeline + your registered dose schedule
/vaccine/register	POST — registers a vaccination plan and computes the dose schedule
/report/<id>	Downloads a PDF report for a saved assessment
/api/history	JSON — all saved assessments
/api/stats	JSON — risk-tier counts
/api/delete/<id>	DELETE — removes a saved assessment
💉 Vaccine dose reminder emails
On registration, an account can optionally include an email address. For every HPV vaccine dose that becomes due (its scheduled date has arrived) and isn't yet marked done, a reminder email is sent once automatically — a background check runs daily inside the Flask process.

To actually send mail, set these environment variables before running app.py:

Variable	Purpose
SMTP_HOST	Your mail server host (e.g. smtp.gmail.com)
SMTP_PORT	Defaults to 587
SMTP_USERNAME / SMTP_PASSWORD	Login credentials for the SMTP account
SMTP_USE_TLS	true (default) or false
MAIL_FROM	From address; defaults to SMTP_USERNAME
REMINDER_CHECK_INTERVAL_SECONDS	How often to check for due doses; defaults to once every 24 hours
If SMTP_HOST isn't set, reminder emails are printed to the console instead of sent, so the app still runs fully without any mail setup.

👥 Team Responsibilities
Member	USN	Responsibility
Manya K	1AY23CS112	Frontend (HTML/CSS/JS)
G. Bhavana	1AY23CS074	Data preprocessing + EDA
Medha M	1AY23CS113	Flask backend + ML integration
Priyanka C	1AY23CS143	Model training + evaluation + docs
Guide: Anitta Antony, Assistant Professor

⚕️ Disclaimer
This system is a decision-support tool built for educational purposes. It is not a substitute for professional medical advice or diagnosis.


