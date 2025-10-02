import numpy as np
import pandas as pd
import xgboost as xgb
from typing import Optional

class CalibratedXGBModel:
    def __init__(self, booster: xgb.Booster, calibrator, threshold: float = 0.5):
        self.booster = booster
        self.calibrator = calibrator
        self.threshold = threshold

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        dmatrix = xgb.DMatrix(X)
        raw_probs = self.booster.predict(dmatrix)
        calibrated_probs = self.calibrator.transform(raw_probs)
        return calibrated_probs

    def predict(self, X: pd.DataFrame, threshold: Optional[float] = None) -> np.ndarray:
        if threshold is None:
            threshold = self.threshold
        return (self.predict_proba(X) >= threshold).astype(int)
