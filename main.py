import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from imblearn.over_sampling import SMOTE
import pickle

# Load dataset
# Download from: https://archive.ics.uci.edu/dataset/383/cervical+cancer+risk+factors
df = pd.read_csv("data.csv")

# Replace '?' with NaN and drop rows with too many missing values
df.replace("?", float("nan"), inplace=True)
df.dropna(thresh=len(df.columns) - 3, inplace=True)

# Select key features used for prediction
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

# Keep only rows where all selected columns are present
df = df[features + [target]].dropna()

X = df[features].astype(float)
y = df[target].astype(int)

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# SMOTE to handle class imbalance
smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(X_train, y_train)

# Train Random Forest model
model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    random_state=42,
    class_weight="balanced",
)
model.fit(X_train_res, y_train_res)

# Evaluate
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"✅ Model Accuracy: {accuracy * 100:.2f}%")
print("\nClassification Report:")
print(classification_report(y_test, y_pred, target_names=["Not At Risk", "At Risk"]))

# Save model and feature list together
with open("model.pkl", "wb") as f:
    pickle.dump({"model": model, "features": features}, f)

print("✅ Model saved as model.pkl")