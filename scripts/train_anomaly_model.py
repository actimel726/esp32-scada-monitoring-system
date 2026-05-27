import os
import pandas as pd
import joblib

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


LOG_FILE = "logs/telemetry_10s.jsonl"
MODEL_FILE = "models/tank_anomaly_model_2.0.joblib"

df = pd.read_json(LOG_FILE, lines=True)


features = [
    "level_mm",
    "level_pct",
    "temp_c",
    "distance_mm",
    "level_change_rate",
    "pump_cmd",
    "pump_feedback",
    "auto_mode",
    "low_alarm",
    "high_alarm",
    "temp_alarm",
    "sensor_fault",
    "system_ok",
    "status_word",
]

df = pd.read_json(LOG_FILE, lines=True)

# Train only on normal records
df = df[df["is_anomaly"] == 0].copy()

df = df.dropna(subset=features)
X = df[features].astype(float)

model = Pipeline([
    ("scaler", StandardScaler()),
    ("isolation_forest", IsolationForest(
        n_estimators=150,
        contamination=0.02,
        random_state=42
    ))
])

model.fit(X)

import os
os.makedirs("models", exist_ok=True)
joblib.dump(model, MODEL_FILE)

print(f"Model trained on {len(X)} telemetry samples.")
print(f"Saved to {MODEL_FILE}")