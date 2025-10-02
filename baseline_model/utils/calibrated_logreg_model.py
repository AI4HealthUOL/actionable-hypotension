import numpy as np

class CalibratedLogRegModel:
    """
    Wrapper class for a calibrated Logistic Regression model.
    Similar in spirit to CalibratedXGBModel.
    """

    def __init__(self, base_model, calibrator):
        """
        Args:
            base_model: Trained sklearn LogisticRegression model
            calibrator: Calibration model (e.g., IsotonicRegression)
        """
        self.base_model = base_model
        self.calibrator = calibrator

    def predict_proba(self, X):
        """
        Returns calibrated probabilities.
        Output format: array of shape (n_samples, 2)
        with [negative class probability, positive class probability]
        """
        # Predict raw probabilities from base model
        raw_probs = self.base_model.predict_proba(X)[:, 1]

        # Apply calibration transformation
        calibrated_probs = self.calibrator.transform(raw_probs)

        # Return as [P(negative), P(positive)]
        return np.column_stack([1 - calibrated_probs, calibrated_probs])

    def predict(self, X, threshold=0.5):
        """
        Predict binary labels using a probability threshold.
        """
        return (self.predict_proba(X)[:, 1] >= threshold).astype(int)
