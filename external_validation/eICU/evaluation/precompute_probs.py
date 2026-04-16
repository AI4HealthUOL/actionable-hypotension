#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
compute_probs.py

Usage:
    python compute_probs.py <CLASS_NAME>

What it does:
  - If CLASS_NAME == "baseline":
        * loads data via load_and_prepare_data_baseline()
        * loads model from "../models/calibrated/baseline_lr.pkl"
    else:
        * loads data via load_and_prepare_data_xgb(table_name="merged_<CLASS_NAME>_features")
        * loads model from "../models/calibrated/xgb_<CLASS_NAME>.pkl"
  - Computes predict_proba and extracts positive-class scores
  - Saves a payload to "probs/<CLASS_NAME>/probs.pkl" (joblib)
"""

import os
import sys
import time
import logging
from pathlib import Path

import joblib
import numpy as np

# Use project loaders (keep your real data functions)
sys.path.append(os.path.abspath(".."))
from evaluation.utils.evaluation_functions import (  # noqa: E402
    load_and_prepare_data_xgb,
    load_and_prepare_data_baseline,
)


def main():
    if len(sys.argv) != 2:
        print("Usage: python compute_probs.py <CLASS_NAME>")
        sys.exit(1)

    CLASS_NAME = sys.argv[1].strip()
    IS_BASELINE = (CLASS_NAME.lower() == "baseline")

    if IS_BASELINE:
        TABLE_NAME = None  # baseline doesn't use the merged_* table
        MODEL_PATH = "../models/calibrated/baseline_lr.pkl"
    else:
        TABLE_NAME = f"merged_{CLASS_NAME}_features"
        MODEL_PATH = f"../models/calibrated/xgb_{CLASS_NAME}.pkl"

    OUT_DIR = Path("probs") / CLASS_NAME
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH = OUT_DIR / "probs.pkl"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("=========== Compute probabilities ===========")
    logging.info("Class name : %s", CLASS_NAME)
    logging.info("Table name : %s", TABLE_NAME if TABLE_NAME else "(baseline loader)")
    logging.info("Model path : %s", MODEL_PATH)
    logging.info("Output path: %s", OUT_PATH)

    # 1) Load test data using your real project loaders
    t0 = time.time()
    if IS_BASELINE:
        # load_and_prepare_data_baseline returns: x_val, y_val, x_test, y_test, _
        _, _, x_test, y_test, _ = load_and_prepare_data_baseline()
    else:
        # load_and_prepare_data_xgb returns: x_train, y_train, x_test, y_test, _
        _, _, x_test, y_test, _ = load_and_prepare_data_xgb(
            table_name=TABLE_NAME,
            drop_treatment_given=True,
            drop_only_2_values=True,
        )
    y_test = np.asarray(y_test).ravel().astype(int)
    logging.info(
        "Loaded test set: n=%d (pos=%d, neg=%d, prev=%.6f) in %.2fs",
        y_test.size,
        int(y_test.sum()),
        int(y_test.size - y_test.sum()),
        float(y_test.mean()),
        time.time() - t0,
    )

    t1 = time.time()
    model = joblib.load(MODEL_PATH)
    logging.info("Model loaded in %.2fs", time.time() - t1)

    # 3) Compute probabilities (positive class score = column 1)
    t2 = time.time()
    probs = model.predict_proba(x_test)
    if getattr(probs, "ndim", 1) == 2 and probs.shape[1] >= 2:
        scores = probs[:, 1]
    else:
        # If a binary estimator returns only one column, build [P0, P1]
        scores = np.asarray(probs, dtype=float).ravel()
        probs = np.stack([1.0 - scores, scores], axis=1)
    scores = np.asarray(scores, dtype=float).ravel()
    logging.info("Computed probabilities in %.2fs", time.time() - t2)

    # 4) Save payload
    payload = {
        "class_name": CLASS_NAME,
        "table_name": TABLE_NAME if TABLE_NAME else "baseline_loader",
        "model_path": MODEL_PATH,
        "n_test": int(y_test.size),
        "labels": y_test,    # ground-truth labels
        "scores": scores,    # P(y=1)
        "probs": probs,      # shape (n, 2): [P0, P1]
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    joblib.dump(payload, OUT_PATH, compress=3)
    logging.info("Saved probabilities to %s", OUT_PATH)
    logging.info("Done.")


if __name__ == "__main__":
    main()