
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from imblearn.over_sampling import SMOTE
import pickle

# ── Load dataset ─────────────────────────────────────────────────────────────
# Download from: https://www.kaggle.com/datasets/loveall/cervical-cancer-risk-classification
df = pd.read_csv("kag_risk_factors_cervical_cancer.csv")

# Replace '?' with NaN and drop rows with too many missing values
df.replace("?", float("nan"), inplace=True)
df.dropna(thresh=len(df.columns) - 3, inplace=True)

# ── Features & target ────────────────────────────────────────────────────────
features = [
    "Age",
    "Number of sexual partners",
    "First sexual intercourse",
    "Num of pregnancies",
    "Smokes",
    "Smokes (years)",
    "Hormonal Contraceptives",
    "IUD",
    "STDs",
    "STDs (number)",
    "STDs:HPV",
]
target = "Biopsy"

df = df[features + [target]].dropna()
X = df[features].astype(float)
y = df[target].astype(int)

# ── Train/test split ─────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ── SMOTE to handle class imbalance ──────────────────────────────────────────
smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

# ── Train Random Forest ───────────────────────────────────────────────────────
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    random_state=42,
    class_weight="balanced",
)
model.fit(X_train_res, y_train_res)

# ── Evaluate ─────────────────────────────────────────────────────────────────
y_pred = model.predict(X_test)
print(f"✅ Accuracy: {accuracy_score(y_test, y_pred) * 100:.2f}%")
print()
print(classification_report(y_test, y_pred, target_names=["Not At Risk", "At Risk"]))

# ── Probability threshold check ───────────────────────────────────────────────
# Verify that the model produces a spread of probabilities,
# which allows the 3-tier (Low / Medium / High) classification to work.
probs = model.predict_proba(X_test)[:, 1]
print(f"Prob range  → min: {probs.min():.3f}  max: {probs.max():.3f}  mean: {probs.mean():.3f}")
print(f"Low  (<0.30): {(probs < 0.30).sum()} samples")
print(f"Med  (0.30–0.60): {((probs >= 0.30) & (probs < 0.60)).sum()} samples")
print(f"High (>=0.60): {(probs >= 0.60).sum()} samples")

# ── Save model ───────────────────────────────────────────────────────────────
with open("model.pkl", "wb") as f:
    pickle.dump({"model": model, "features": features}, f)

print("\n✅ Model saved as model.pkl")
