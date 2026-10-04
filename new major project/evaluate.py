
"""
evaluate.py — Full model evaluation with confusion matrix, ROC curve, and metrics.
Run: python evaluate.py
"""

import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    roc_auc_score, roc_curve, ConfusionMatrixDisplay
)
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE

print("Loading dataset...")
df = pd.read_csv("kag_risk_factors_cervical_cancer.csv", na_values="?")

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

df = df[features + [target]]
df = df.fillna(df.median(numeric_only=True))

X = df[features].astype(float)
y = df[target].astype(int)

# Same split as train_model.py
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Apply SMOTE on train only
smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

# ── Load saved model ───────────────────────────────────────────────────────────
print("Loading model.pkl...")
with open("model.pkl", "rb") as f:
    artifact = pickle.load(f)
model = artifact["model"]

# ── Predict ────────────────────────────────────────────────────────────────────
y_pred = model.predict(X_test)
y_prob = model.predict_proba(X_test)[:, 1]

# ── Print metrics ──────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
print(f"  Accuracy  : {accuracy_score(y_test, y_pred) * 100:.2f}%")
print(f"  ROC-AUC   : {roc_auc_score(y_test, y_prob):.4f}")
print("=" * 55)
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=["Not At Risk", "At Risk"]))

# ── Feature importances ────────────────────────────────────────────────────────
importances = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)
print("Feature Importances:")
for feat, imp in importances.items():
    bar = "█" * int(imp * 100)
    print(f"  {feat:<35} {imp:.4f}  {bar}")

# ── Plots ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
fig.suptitle(
    "Model Evaluation — Cervical Cancer Risk Predictor",
    fontsize=14, fontweight="bold", color="#6d28d9"
)

# 1. Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=["Not At Risk", "At Risk"]
)
disp.plot(ax=axes[0], colorbar=False, cmap="Purples")
axes[0].set_title("Confusion Matrix")

# 2. ROC Curve
fpr, tpr, _ = roc_curve(y_test, y_prob)
auc = roc_auc_score(y_test, y_prob)
axes[1].plot(fpr, tpr, color="#6d28d9", lw=2, label=f"AUC = {auc:.3f}")
axes[1].plot([0, 1], [0, 1], "k--", lw=1)
axes[1].fill_between(fpr, tpr, alpha=0.08, color="#6d28d9")
axes[1].set_xlabel("False Positive Rate")
axes[1].set_ylabel("True Positive Rate")
axes[1].set_title("ROC Curve")
axes[1].legend(loc="lower right")
axes[1].spines["top"].set_visible(False)
axes[1].spines["right"].set_visible(False)

# 3. Feature Importance Bar Chart
colors = ["#6d28d9" if i == 0 else "#a78bfa" for i in range(len(importances))]
axes[2].barh(importances.index[::-1], importances.values[::-1],
             color=colors[::-1], edgecolor="white")
axes[2].set_xlabel("Importance Score")
axes[2].set_title("Feature Importances")
axes[2].spines["top"].set_visible(False)
axes[2].spines["right"].set_visible(False)

plt.tight_layout()
plt.savefig("evaluation_report.png", dpi=150, bbox_inches="tight")
plt.show()

print("\n" + "=" * 55)
print("  evaluation_report.png saved!")
print("=" * 55)
