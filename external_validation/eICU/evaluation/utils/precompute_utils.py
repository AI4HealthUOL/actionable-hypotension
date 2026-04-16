# utils/precompute_utils.py
# Heavy computations + caching (NumPy .npz + small JSON meta).
# Only matplotlib is used downstream; no Plotly.

from __future__ import annotations
import os, json, hashlib, logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Tuple

import numpy as np
from sklearn.metrics import (
    roc_curve, roc_auc_score,
    precision_recall_curve, average_precision_score
)
from sklearn.calibration import calibration_curve
from scipy.ndimage import gaussian_filter1d
from scipy.integrate import trapezoid

# ---------- basic cache helpers ----------

CACHE_DIR = "cache"

def _to_unicode_array(strings):
    """Return a NumPy Unicode array (no object dtype)."""
    strings = [str(s) for s in strings]
    max_len = max(1, max(len(s) for s in strings))
    return np.array(strings, dtype=f"<U{max_len}")

def _safe_numeric(arr, dtype="float32"):
    """
    Convert to numeric ndarray without object dtype.
    Returns ndarray or None if conversion is impossible.
    """
    a = np.asarray(arr)
    if a.dtype == object:
        try:
            a = a.astype(dtype)
        except Exception:
            return None
    else:
        a = a.astype(dtype, copy=False)
    return a

def _reduce_object_array_of_arrays(obj):
    """
    If SHAP returns an object array (e.g. list of per-class matrices),
    try to stack along a new last axis and reduce to a 2D matrix:
      - if 2 classes: take last class
      - else: mean over classes
    """
    try:
        stacked = np.stack(list(obj), axis=-1)  # (..., n_classes)
        if stacked.ndim == 3:  # (n_samples, n_features, n_classes)
            return stacked[..., -1] if stacked.shape[-1] == 2 else stacked.mean(axis=-1)
        return stacked
    except Exception:
        raise ValueError("SHAP values/base_values are object-dtype and could not be stacked to numeric.")

def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _save_npz(path: str, **kwargs) -> None:
    _ensure_dir(os.path.dirname(path))
    np.savez_compressed(path, **kwargs)

def _load_npz(path: str) -> Dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as f:
        return {k: f[k] for k in f.files}

def _atomic_write_text(path: str, text: str) -> None:
    """Write text atomically to avoid truncated meta files."""
    _ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)

def _save_json(path: str, obj: dict) -> None:
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))

def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)

def _hash_arrays(*arrays: np.ndarray) -> str:
    h = hashlib.sha1()
    for a in arrays:
        a = np.asarray(a)
        h.update(str(a.shape).encode())
        h.update(str(a.dtype).encode())
        h.update(a.tobytes())
    return h.hexdigest()[:24]

def _ndarray_summary_with_hash(arr: Optional[np.ndarray]) -> Optional[dict]:
    """Return a small, JSON-serializable signature for an array (for meta only)."""
    if arr is None:
        return None
    a = np.asarray(arr).ravel()
    if a.size == 0:
        return {"n": 0, "hash": None, "min": None, "max": None}
    return {
        "n": int(a.size),
        "hash": _hash_arrays(a),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }

# ---------- precompute: curves ----------

@dataclass
class CurveParams:
    do_bootstrap: bool = True
    bootstrap_iterations: int = 1000
    bootstrap_alpha: float = 0.95
    cal_n_bins: int = 10
    cal_strategy: str = "quantile"
    dca_thresholds: Optional[np.ndarray] = None
    dca_smoothing_sigma: float = 1.0

def _bootstrap_auc_ci(y_true: np.ndarray,
                      y_prob: np.ndarray,
                      iters: int,
                      alpha: float,
                      seed: int = 42) -> Tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    aucs = []
    for _ in range(iters):
        idx = rng.integers(0, n, n)
        yt, yp = y_true[idx], y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, yp))
    if not aucs:
        return np.nan, np.nan
    lo = np.percentile(aucs, (1 - alpha) / 2 * 100)
    hi = np.percentile(aucs, (alpha + (1 - alpha) / 2) * 100)
    return float(lo), float(hi)


def compute_net_benefit(y_true: np.ndarray,
                        y_prob: np.ndarray,
                        thresholds: np.ndarray) -> np.ndarray:
    """
    Compute net benefit for a set of thresholds.

    Net Benefit formula:
        NB(pt) = (TP / N) - (FP / N) * (pt / (1 - pt))

    Args:
        y_true: Array of true binary labels (0 or 1).
        y_prob: Array of predicted probabilities (same length as y_true).
        thresholds: Array of threshold values between 0 and 1.

    Returns:
        np.ndarray of net benefit values for each threshold.
    """
    y_true = np.asarray(y_true).ravel().astype(int)
    y_prob = np.asarray(y_prob).ravel()
    th = np.asarray(thresholds).ravel()
    N = y_true.size
    eps = 1e-12  # to avoid division by zero

    net_benefits = np.empty_like(th, dtype=float)
    for i, pt in enumerate(th):
        pt = float(np.clip(pt, eps, 1.0 - eps))  # clamp threshold to (0,1)
        y_pred = (y_prob >= pt)
        TP = np.sum((y_true == 1) & (y_pred == 1))
        FP = np.sum((y_true == 0) & (y_pred == 1))
        net_benefits[i] = (TP / N) - (FP / N) * (pt / (1.0 - pt))

    return net_benefits



def _params_meta_dict(class_name: str, key: str, params: CurveParams) -> dict:
    """Make a JSON-safe meta payload for curves."""
    p = asdict(params)
    # replace ndarray with summary+hash
    p["dca_thresholds"] = _ndarray_summary_with_hash(params.dca_thresholds)
    return {"class_name": class_name, "key": key, **p}

def precompute_curves(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    class_name: str,
    params: CurveParams = CurveParams(),
    force: bool = False,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Compute ROC (with optional bootstrap CI), PR, calibration (ECE),
    and decision curve (with area under NB). Save to cache and return dict.
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = np.asarray(y_prob).ravel()

    # build a unique key (include dca_thresholds signature!)
    key_core = _hash_arrays(y_true, y_prob)
    thr_sig = "auto" if params.dca_thresholds is None else _hash_arrays(np.asarray(params.dca_thresholds))
    key = (
        f"{class_name}-curves-{key_core}"
        f"-b{params.bootstrap_iterations}-a{params.bootstrap_alpha}"
        f"-bins{params.cal_n_bins}-{params.cal_strategy}"
        f"-thr{thr_sig}"
    )
    npz_path = os.path.join(CACHE_DIR, class_name, f"{key}.npz")
    meta_path = os.path.join(CACHE_DIR, class_name, f"{key}.json")

    if (not force) and os.path.exists(npz_path) and os.path.exists(meta_path):
        try:
            out = _load_npz(npz_path)
            out["meta"] = _load_json(meta_path)
            return out
        except Exception as e:
            logging.warning(f"[precompute_curves] Cache exists but failed to load ({e}). Recomputing and overwriting...")

    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc = roc_auc_score(y_true, y_prob)
    auc_lo, auc_hi = (np.nan, np.nan)
    if params.do_bootstrap:
        auc_lo, auc_hi = _bootstrap_auc_ci(
            y_true, y_prob, params.bootstrap_iterations, params.bootstrap_alpha, seed=seed
        )

    # PR
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    ap = average_precision_score(y_true, y_prob)
    baseline = y_true.mean()  # positive class rate

    # Calibration + ECE
    prob_true, prob_pred = calibration_curve(
        y_true, y_prob, n_bins=params.cal_n_bins, strategy=params.cal_strategy
    )
    hist_counts = np.histogram(y_prob, bins=params.cal_n_bins)[0]
    total = np.sum(hist_counts)
    valid = min(len(prob_true), len(prob_pred), len(hist_counts))
    ece = float(np.sum((hist_counts[:valid] / total) * np.abs(prob_true[:valid] - prob_pred[:valid])))

    # Decision curve
    if params.dca_thresholds is None:
        # Create thresholds from ~0 up to slightly beyond the max predicted probability
        t_max = min(0.999, float(y_prob.max()) + 0.1)
        thr = np.linspace(0.0, t_max, 200)
    else:
        thr = np.asarray(params.dca_thresholds).ravel()

    # Compute net benefit for model predictions and for "refer-all" / "refer-none" strategies
    nb_model = compute_net_benefit(y_true, y_prob, thr)
    nb_all   = compute_net_benefit(y_true, np.ones_like(y_prob), thr)   # always refer all
    nb_none  = compute_net_benefit(y_true, np.zeros_like(y_prob), thr)  # refer none

    # Optionally smooth only the model curve
    if params.dca_smoothing_sigma and params.dca_smoothing_sigma > 0:
        nb_model = gaussian_filter1d(nb_model, sigma=params.dca_smoothing_sigma)

    # Calculate AUNB (area under net benefit curve) for each strategy
    aunbc = np.array([
        trapezoid(nb_model, thr),
        trapezoid(nb_all,   thr),
        trapezoid(nb_none,  thr)
    ], dtype=float)

    payload = dict(
        fpr=fpr, tpr=tpr, auc=np.array([auc], dtype=float),
        auc_ci=np.array([auc_lo, auc_hi], dtype=float),
        precision=precision, recall=recall, ap=np.array([ap], dtype=float),
        baseline=np.array([baseline], dtype=float),
        prob_true=prob_true, prob_pred=prob_pred, ece=np.array([ece], dtype=float),
        dca_thresholds=thr, nb_model=nb_model, nb_all=nb_all, nb_none=nb_none,
        aunbc=aunbc,
    )
    _save_npz(npz_path, **payload)
    _save_json(meta_path, _params_meta_dict(class_name, key, params))

    payload["meta"] = _load_json(meta_path)
    return payload

def load_curves_cache(class_name: str, key: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a cached curve package either by explicit key or the latest file for the class.
    """
    cache_dir = os.path.join(CACHE_DIR, class_name)
    files = [] if not os.path.isdir(cache_dir) else sorted(
        [f for f in os.listdir(cache_dir) if f.endswith(".npz") and "-curves-" in f]
    )
    if key:
        npz_path = os.path.join(cache_dir, f"{key}.npz")
        meta_path = os.path.join(cache_dir, f"{key}.json")
    else:
        if not files:
            raise FileNotFoundError(f"No cached curves for class '{class_name}'.")
        fname = files[-1]
        npz_path = os.path.join(cache_dir, fname)
        meta_path = npz_path.replace(".npz", ".json")
    out = _load_npz(npz_path)
    try:
        out["meta"] = _load_json(meta_path)
    except Exception as e:
        logging.warning(f"[load_curves_cache] Failed to load meta ({e}). Returning payload without meta.")
        out["meta"] = {}
    return out

# ---------- precompute: SHAP for tree models ----------

from shap import TreeExplainer
import shap

@dataclass
class ShapParams:
    n_samples: Optional[int] = 5000
    random_state: int = 42
    store_X: bool = True   # store feature values to enable colored beeswarm
    dtype: str = "float32"

def precompute_shap_tree(
    model,
    X,
    class_name: str,
    params: ShapParams = ShapParams(),
    force: bool = False
) -> Dict[str, Any]:
    import pandas as pd
    if isinstance(X, pd.DataFrame):
        feats = X.columns.to_list()
        Xarr = X.values
    else:
        Xarr = np.asarray(X)
        feats = [f"f{i}" for i in range(Xarr.shape[1])]

    rng = np.random.default_rng(params.random_state)
    if params.n_samples is not None and params.n_samples < Xarr.shape[0]:
        idx = np.sort(rng.choice(Xarr.shape[0], params.n_samples, replace=False))
        Xuse = Xarr[idx]
    else:
        idx = np.arange(Xarr.shape[0])
        Xuse = Xarr

    key_core = _hash_arrays(Xuse)
    key = f"{class_name}-shap-{Xuse.shape[0]}x{Xuse.shape[1]}-{key_core}"
    npz_path = os.path.join(CACHE_DIR, class_name, f"{key}.npz")
    meta_path = os.path.join(CACHE_DIR, class_name, f"{key}.json")

    if (not force) and os.path.exists(npz_path) and os.path.exists(meta_path):
        try:
            out = _load_npz(npz_path)
            out["meta"] = _load_json(meta_path)
            return out
        except Exception as e:
            logging.warning(f"[precompute_shap_tree] Cache exists but failed to load ({e}). Recomputing and overwriting...")

    explainer = TreeExplainer(model)
    exp = explainer(Xuse)  # shap.Explanation

    # ---- values (always numeric, 2D) ----
    values = np.asarray(exp.values)
    if values.dtype == object:
        values = _reduce_object_array_of_arrays(values)
    values = values.astype(params.dtype, copy=False)

    # ---- base_values (numeric, 1D) ----
    base_values = np.asarray(exp.base_values)
    if base_values.dtype == object:
        base_values = _reduce_object_array_of_arrays(base_values)
    base_values = np.atleast_1d(base_values).astype(params.dtype, copy=False)

    save_dict = dict(
        values=values,                                       # (n_samples, n_features)
        base_values=base_values,                             # (n_samples,) or (1,)
        feature_names=_to_unicode_array(feats),              # <U* (no object)
        row_index=idx.astype(np.int64)                       # int64
    )

    # ---- X_sample optional & safe numeric ----
    if params.store_X:
        Xnum = _safe_numeric(Xuse, dtype=params.dtype)
        if Xnum is not None:
            save_dict["X_sample"] = Xnum

    _save_npz(npz_path, **save_dict)
    _save_json(meta_path, {"class_name": class_name, "key": key, **asdict(params)})

    out = _load_npz(npz_path)  # allow_pickle=False
    try:
        out["meta"] = _load_json(meta_path)
    except Exception:
        out["meta"] = {"class_name": class_name, "key": key, **asdict(params)}
    return out

def load_shap_cache(class_name: str, key: Optional[str] = None) -> Dict[str, Any]:
    cache_dir = os.path.join(CACHE_DIR, class_name)
    files = [] if not os.path.isdir(cache_dir) else sorted(
        [f for f in os.listdir(cache_dir) if f.endswith(".npz") and "-shap-" in f]
    )
    if key:
        npz_path = os.path.join(cache_dir, f"{key}.npz")
        meta_path = os.path.join(cache_dir, f"{key}.json")
    else:
        if not files:
            raise FileNotFoundError(f"No cached SHAP for class '{class_name}'.")
        fname = files[-1]
        npz_path = os.path.join(cache_dir, fname)
        meta_path = npz_path.replace(".npz", ".json")
    out = _load_npz(npz_path)
    try:
        out["meta"] = _load_json(meta_path)
    except Exception as e:
        logging.warning(f"[load_shap_cache] Failed to load meta ({e}). Returning payload without meta.")
        out["meta"] = {}
    return out

def shap_explanation_from_cache(shap_cache: Dict[str, Any]) -> shap.Explanation:
    """
    Reconstruct a shap.Explanation. Works even if X_sample was not stored.
    """
    values = shap_cache["values"]                   # 2D numeric
    base_values = shap_cache["base_values"]
    X_sample = shap_cache.get("X_sample", None)     # may be None
    feat_arr = shap_cache.get("feature_names", None)
    feature_names = [str(s) for s in np.asarray(feat_arr).tolist()] if feat_arr is not None else None
    return shap.Explanation(values=values,
                            base_values=base_values,
                            data=X_sample,
                            feature_names=feature_names)