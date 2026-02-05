import os
import sys
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb

#sys.path.insert(0, '/dss/work/rirg2545/actionable-hypotension/calibration')
sys.path.insert(0, '/dss/work/rirg2545/actionable-hypotension/utils')

print("CWD:", os.getcwd())
print("\n--- sys.path ---")
for p in sys.path:
    print(p)

from db_interface import get_engine
from utils.calibrated_xgb_model import CalibratedXGBModel
import joblib

UNCALIBRATED_MODELS_DIR = "../models/uncalibrated"
CALIBRATED_MODELS_DIR = "../models/calibrated"

def load_and_prepare_validation_data(table_name, drop_treatment_given=False, drop_only_2_values=False):
    
    print("CWD:", os.getcwd())
    print("\n--- sys.path ---")
    for p in sys.path:
        print(p)
    
    

    engine = get_engine()
    df = pd.read_sql(f"""
        SELECT * FROM ce_approach.{table_name}
        WHERE split IN ('val', 'test')
    """, engine)

    drop_cols = ["subject_id", "icustay_id", "context_start", "context_end"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])
    
    
    df["label"] = df["positive_event"].astype(int)

    excluded = {"positive_event", "positive_sample", "split", "label"}
    
    if drop_treatment_given:
        df = df.drop(columns=["treatment_given"])
    if drop_only_2_values:
        df = df.drop(columns=["only_2_values"])
    
    feature_cols = [c for c in df.columns if c not in excluded]

    val_df  = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]

    x_val = val_df[feature_cols]
    y_val = val_df["label"]

    return x_val, y_val


def calibrate_xgb_model_isotonic(uncalibrated_model, x_val, y_val):
    """
    Calibrates an XGBoost model using Isotonic Regression on validation data.

    Args:
        model: Trained XGBoost Booster or XGBClassifier
        x_val (pd.DataFrame): Validation features
        y_val (pd.Series or np.ndarray): Validation labels

    Returns:
        iso: Trained IsotonicRegression calibrator
    """
    # Get raw predicted probabilities
    if isinstance(uncalibrated_model, xgb.Booster):
        dval = xgb.DMatrix(x_val, missing=np.nan)
        y_val_pred = uncalibrated_model.predict(dval)
    elif isinstance(uncalibrated_model, xgb.XGBClassifier):
        y_val_pred = uncalibrated_model.predict_proba(x_val)[:, 1]
    else:
        raise ValueError("Unsupported model type. Must be Booster or XGBClassifier.")

    # Fit Isotonic Regression on sorted predictions
    sorted_idx = np.argsort(y_val_pred)
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(y_val_pred[sorted_idx], y_val.iloc[sorted_idx] if hasattr(y_val, "iloc") else y_val[sorted_idx])

    return iso

def load_calibrate_and_save_model(model_name, table_name, drop_treatment_given=False, drop_only_2_values=False):
    x_val, y_val = load_and_prepare_validation_data(table_name, drop_treatment_given=drop_treatment_given, drop_only_2_values=drop_only_2_values)
    
    model_path = os.path.join(UNCALIBRATED_MODELS_DIR, f"{model_name}.json")
    uncalibrated_model = xgb.Booster()
    uncalibrated_model.load_model(model_path)
    
    iso = calibrate_xgb_model_isotonic(uncalibrated_model=uncalibrated_model, x_val=x_val, y_val=y_val)
    
    calibrated_model = CalibratedXGBModel(uncalibrated_model, iso)
    
    joblib.dump(calibrated_model, os.path.join(CALIBRATED_MODELS_DIR, f"{model_name}.pkl"))