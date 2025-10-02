#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
deeproc_cli.py

Usage:
    python deeproc_cli.py --class-name <TASK> [--tpr low,high ...] [--probs-file PATH]

What it does:
  - Loads precomputed probabilities & labels from "probs/<CLASS_NAME>/probs.pkl"
    (or from --probs-file if provided).
  - Runs DeepROC analysis for the requested TPR groups.
  - Saves JSON metrics and the DeepROC object under "figures/<CLASS_NAME>/".

Expected payload (from compute_probs.py):
  - dict with keys: "labels" (1D int), "scores" (1D float, P(y=1)) and/or "probs" ((n,2))
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path

import joblib
import numpy as np

# DeepROC
from deeproc.DeepROC import DeepROC


# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(
        description="DeepROC evaluation using precomputed probabilities.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--class-name",
        type=str,
        required=True,
        help="Task name. For baseline: 'baseline'. For XGB: e.g. 'noninv', 'mix', ...",
    )
    p.add_argument(
        "--tpr",
        action="append",
        default=None,
        help="Optional: TPR ranges as 'low,high'. Can be repeated. "
             "Example: --tpr 0.70,0.80 --tpr 0.75,0.85",
    )
    p.add_argument(
        "--probs-file",
        type=str,
        default=None,
        help="Optional override path to probs.pkl. Default: probs/<CLASS_NAME>/probs.pkl",
    )
    return p.parse_args()


def parse_tpr_groups(arg_list):
    """Parse --tpr arguments into tuples or return default ranges."""
    if not arg_list:
        return [(0.70, 0.80), (0.75, 0.85), (0.80, 0.90)]
    groups = []
    for item in arg_list:
        lo, hi = map(float, item.split(","))
        if not (0.0 <= lo < hi <= 1.0):
            raise ValueError(f"Invalid TPR range: {item}")
        groups.append((lo, hi))
    return groups


def _load_probs_payload(default_path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load labels and scores from a joblib payload; fallback from 'probs' to 'scores' if needed."""
    if not default_path.exists():
        raise FileNotFoundError(f"Probs file not found: {default_path}")
    payload = joblib.load(default_path)

    # labels
    if "labels" not in payload:
        raise KeyError("Payload is missing 'labels'.")
    y = np.asarray(payload["labels"]).ravel().astype(int)

    # scores (P(y=1))
    if "scores" in payload:
        scores = np.asarray(payload["scores"], dtype=float).ravel()
    elif "probs" in payload:
        probs = np.asarray(payload["probs"], dtype=float)
        if probs.ndim != 2 or probs.shape[1] < 2:
            raise ValueError("Payload 'probs' must have shape (n, 2).")
        scores = probs[:, 1]
    else:
        raise KeyError("Payload must contain 'scores' or 'probs'.")

    if scores.shape[0] != y.shape[0]:
        raise ValueError(f"Length mismatch: scores({scores.shape[0]}) != labels({y.shape[0]}).")

    return scores, y, payload


# ---------------- Main ----------------
def main():
    args = parse_args()

    CLASS_NAME = args.class_name.strip()
    OUT_DIR = Path("figures") / CLASS_NAME
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    TPR_GROUPS = parse_tpr_groups(args.tpr)

    # Determine probs file path
    probs_path = Path(args.probs_file) if args.probs_file else (Path("probs") / CLASS_NAME / "probs.pkl")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info("=========== DeepROC evaluation (using precomputed probs) ===========")
    logging.info("Class name : %s", CLASS_NAME)
    logging.info("Probs file : %s", probs_path)
    logging.info("Output dir : %s", OUT_DIR)
    logging.info("TPR groups : %s", TPR_GROUPS)

    # 1) Load precomputed scores & labels
    t0 = time.time()
    y_test_scores, y_test, payload = _load_probs_payload(probs_path)
    logging.info(
        "Loaded payload in %.2fs: n=%d (pos=%d, neg=%d, prev=%.6f)",
        time.time() - t0,
        y_test.size,
        int(y_test.sum()),
        int(y_test.size - y_test.sum()),
        float(y_test.mean()),
    )

    # 2) DeepROC analysis
    t1 = time.time()
    dra = DeepROC(predicted_scores=y_test_scores, labels=y_test, poslabel=1)
    dra.setGroupsBy(groupAxis="TPR", groups=TPR_GROUPS, groupByClosestInstance=False)
    measure_list = dra.analyze(forFolds=False, verbose=False)
    t_elapsed = time.time() - t1
    logging.info("DeepROC analysis time: %.2f seconds.", t_elapsed)

    # 3) Save outputs (metrics + metadata)
    meta = {
        "class_name": CLASS_NAME,
        "probs_file": str(probs_path),
        "n_test": int(y_test.size),
        "n_pos": int(y_test.sum()),
        "n_neg": int(y_test.size - y_test.sum()),
        "prevalence": float(y_test.mean()),
        "tpr_groups": TPR_GROUPS,
        "deeproc_runtime_sec": round(t_elapsed, 2),
        "source_table": payload.get("table_name", None),
        "model_path": payload.get("model_path", None),
        "timestamp_probs": payload.get("timestamp", None),
    }

    metrics_json = OUT_DIR / f"DeepROC_{CLASS_NAME}_groups.json"
    with open(metrics_json, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "groups": measure_list}, fh, ensure_ascii=False, indent=2)
    logging.info("Metrics saved to %s", metrics_json)

    dra_path = OUT_DIR / f"DeepROC_{CLASS_NAME}_object.pkl"
    joblib.dump(dra, dra_path)
    logging.info("DeepROC object saved to %s", dra_path)

    logging.info("Evaluation finished.")


if __name__ == "__main__":
    main()