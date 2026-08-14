import joblib
import xgboost as xgb

old_model = joblib.load("models/xgboost_bankruptcy.joblib")
old_model.save_model("models/xgboost_bankruptcy.json")

print("Re-saved successfully")
