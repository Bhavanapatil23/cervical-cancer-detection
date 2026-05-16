# 🎗️ CervixGuard AI — Cervical Cancer Risk Assessment System
**BCS685 | Acharya Institute of Technology | Dept. of CSE**

## 📁 Project Structure

```
cervical_cancer_app/
├── app.py                  ← Flask backend (main server)
├── train_model.py          ← Train ML model (run first!)
├── evaluate.py             ← Model evaluation + plots
├── requirements.txt        ← Python dependencies
├── .env                    ← Database credentials
├── kag_risk_factors_cervical_cancer.csv  ← Dataset
├── model.pkl               ← Saved model (generated after training)
├── templates/
│   ├── index.html          ← Assessment form page
│   ├── result.html         ← Risk result + recommendations
│   ├── dashboard.html      ← Analytics dashboard
│   └── vaccine.html        ← HPV vaccine reminder
└── static/
    ├── css/style.css       ← All styles
    └── js/main.js          ← Form interactions
```

## 🚀 How to Run

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Set up PostgreSQL
```sql
CREATE DATABASE cervical_cancer_db;
```
Edit `.env` with your PostgreSQL credentials.

> ⚠️ If you don't have PostgreSQL, the app still works! It will just skip saving to DB and show predictions normally.

### Step 3 — Place the dataset
Put `kag_risk_factors_cervical_cancer.csv` in the project root.  
Download from: https://www.kaggle.com/datasets/loveall/cervical-cancer-risk-classification

### Step 4 — Train the model
```bash
python train_model.py
```
This generates `model.pkl`.

### Step 5 — Run the Flask app
```bash
python app.py
```
Open: http://localhost:5000

### Step 6 — (Optional) Evaluate model
```bash
python evaluate.py
```
Generates `evaluation_report.png` with confusion matrix and ROC curves.

---

## 🧠 ML Model Details

| Property | Value |
|---|---|
| Algorithm | Random Forest |
| Classes | Low / Medium / High |
| Features | 11 health risk factors |
| Class Imbalance | SMOTE oversampling |
| Accuracy | ~95% |

### Features Used
- Age
- Number of sexual partners
- Age at first sexual intercourse
- Number of pregnancies
- Smoking status + years
- Hormonal contraceptives
- IUD usage
- STDs count + HPV diagnosis

---

## 🌐 Pages

| Route | Description |
|---|---|
| `/` | Risk assessment form |
| `/predict` | POST — runs prediction |
| `/dashboard` | Analytics with charts |
| `/vaccine` | HPV vaccine dose reminder |

---

## 👥 Team Responsibilities

| Member | USN | Responsibility |
|---|---|---|
| Manya K | 1AY23CS112 | Frontend (HTML/CSS/JS) |
| G. Bhavana | 1AY23CS074 | Data preprocessing + EDA |
| Medha M | 1AY23CS113 | Flask backend + ML integration |
| Priyanka C | 1AY23CS143 | Model training + evaluation + docs |

**Guide:** Anitta Antony, Assistant Professor

---

## ⚕️ Disclaimer
This system is a decision-support tool built for educational purposes.  
It is **not** a substitute for professional medical advice or diagnosis.