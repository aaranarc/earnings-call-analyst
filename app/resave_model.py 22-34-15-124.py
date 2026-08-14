import joblib
import xgboost as xgb

# load the old model (works, just warns)
old_model = joblib.load("models/xgboost_bankruptcy.joblib")

# save it using XGBoost's native format instead of pickle
old_model.save_model("models/xgboost_bankruptcy.json")

print("Re-saved successfully")