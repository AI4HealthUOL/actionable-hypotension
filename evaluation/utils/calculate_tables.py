import os
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_curve, roc_auc_score, precision_recall_curve, average_precision_score,
    confusion_matrix, brier_score_loss
)
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression

# ---------------------------
# Helpers (robust, shape-safe)
# ---------------------------

def _safe_div(num, den):
    """Safe division that returns 0 when denominator is 0."""
    den = np.asarray(den, dtype=float)
    return np.divide(num, den, out=np.zeros_like(np.asarray(num, dtype=float)), where=den != 0)

def _ensure_1d(a):
    """Return 1-D positive-class scores if a is (n,2); otherwise ravel."""
    a = np.asarray(a)
    return a[:, 1] if (a.ndim == 2 and a.shape[1] == 2) else a.ravel()

def _to_scalar(x):
    """Force any scalar-like into a Python float."""
    arr = np.asarray(x).ravel()
    if arr.size == 0:
        raise ValueError("Empty scalar-like value.")
    return float(arr[0])

def _apply_rule(scores, thr, rule: str = ">"):
    """
    Apply the classification rule consistently.
    sklearn's roc_curve uses 'score > thr' to define positives; default matches that.
    """
    scores = np.asarray(scores).ravel()
    thr = _to_scalar(thr)
    if rule == ">":
        return (scores > thr).astype(int)
    elif rule == ">=":
        return (scores >= thr).astype(int)
    else:
        raise ValueError("rule must be '>' or '>='")

# ----------------------------------------------
# Threshold selectors (support strategy + rule)
# ----------------------------------------------

def find_threshold_for_target_recall(
    y_true, y_prob, target_recall: float,
    strategy: str = "closest",   # "closest" | "ge" | "quantile_pos"
    rule: str = ">",             # use ">" to match sklearn's roc_curve convention
):
    """
    Select a single scalar threshold according to the chosen strategy.
      - "closest":      pick the ROC point whose TPR is closest to target_recall.
      - "ge":           first ROC point with TPR >= target_recall.
      - "quantile_pos": set threshold at the (1 - target) quantile of positive scores.
    Returns (threshold, realized_recall_on_selection_set).

    Note on `rule`:
      - sklearn defines positives as y_score > thr inside roc_curve.
      - If you later evaluate with '>=' instead, the realized recall can shift.
      - To keep behavior aligned, use the same rule throughout (default '>').
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)

    if strategy == "quantile_pos":
        pos_scores = y_prob[y_true == 1]
        if pos_scores.size == 0:
            raise ValueError("No positives in data.")
        q = float(np.clip(1.0 - target_recall, 0.0, 1.0))
        # robust quantile; 'midpoint' is stable with ties
        thr = float(np.quantile(pos_scores, q, method="midpoint"))
        pred = _apply_rule(y_prob, thr, rule=rule)
        tp = np.sum((y_true == 1) & (pred == 1))
        P = np.sum(y_true == 1)
        realized = float(tp / P) if P else 0.0
        return thr, realized

    # ROC-based selection
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)

    # If you truly want to evaluate with '>=' later, nudging thresholds up
    # preserves the same positive set (optional):
    if rule == ">=":
        thresholds = np.nextafter(thresholds, np.inf)

    if strategy == "ge":
        idx = np.where(tpr >= target_recall)[0]
        i = int(idx[0]) if idx.size else int(len(tpr) - 1)
        return float(thresholds[i]), float(tpr[i])

    # "closest"
    i = int(np.argmin(np.abs(tpr - target_recall)))
    return float(thresholds[i]), float(tpr[i])

def interpolated_recall_threshold(y_true, y_prob, target_recall: float):
    """
    Interpolated (probabilistic) thresholding to hit target TPR exactly in expectation.
    Returns (thr_hi, thr_lo, p, expected_TPR):
      - Predict positive for scores > thr_hi.
      - For scores in (thr_lo, thr_hi], sample positives with probability p.
    Useful to report what would be needed to exactly match the target on average.
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)

    # Find ROC segment containing target_recall
    i = np.searchsorted(tpr, target_recall, side="left")
    if i == 0:
        return float(thresholds[0]), float(thresholds[0]), 0.0, float(tpr[0])
    if i >= len(tpr):
        return float(thresholds[-1]), float(thresholds[-1]), 0.0, float(tpr[-1])

    t_lo, r_lo = thresholds[i - 1], tpr[i - 1]
    t_hi, r_hi = thresholds[i],     tpr[i]
    if r_hi == r_lo:
        return float(t_hi), float(t_lo), 0.0, float(r_hi)

    p = float((target_recall - r_lo) / (r_hi - r_lo))
    r_exp = float(r_lo + p * (r_hi - r_lo))
    return float(t_hi), float(t_lo), p, r_exp

def get_youden_threshold(y_true, y_prob):
    """Return (threshold, fpr, tpr) at Youden's J; threshold is a float."""
    y_prob = _ensure_1d(y_prob)
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    j = tpr - fpr
    i = int(np.argmax(j))
    return float(thresholds[i]), float(fpr[i]), float(tpr[i])

# ---------------------------------
# Counts & rates at a given threshold
# ---------------------------------

def counts_at_threshold(y_true, y_prob, thr, rule: str = ">"):
    """Return TP, FP, TN, FN at threshold using the given rule."""
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)
    y_pred = _apply_rule(y_prob, thr, rule=rule)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return int(tp), int(fp), int(tn), int(fn)

def rates_from_counts(tp, fp, tn, fn):
    """Return Sensitivity, Specificity, PPV, NPV from counts."""
    sens = _safe_div(tp, tp + fn)
    spec = _safe_div(tn, tn + fp)
    ppv  = _safe_div(tp, tp + fp)
    npv  = _safe_div(tn, tn + fn)
    f1   = _safe_div(2 * tp, 2 * tp + fp + fn)  # add this
    return float(sens), float(spec), float(ppv), float(npv), float(f1)

# -------------------------------------------
# Bootstrap CI for fixed-threshold statistics
# -------------------------------------------

def bootstrap_ci_fixed_threshold(
    y_true, y_prob, thr,
    n_boot=1000, alpha=0.95, seed=123, rule: str = ">"
):
    """Non-parametric bootstrap CIs for counts & rates at a fixed threshold."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)
    n = len(y_true)

    tpL=[]; fpL=[]; tnL=[]; fnL=[]; f1L = []  # add this list
    sensL=[]; specL=[]; ppvL=[]; npvL=[]
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt = y_true[idx]; yp = y_prob[idx]
        tp, fp, tn, fn = counts_at_threshold(yt, yp, thr, rule=rule)
        tpL.append(tp); fpL.append(fp); tnL.append(tn); fnL.append(fn)
        s, c, p, n_, f1 = rates_from_counts(tp, fp, tn, fn)
        sensL.append(s); specL.append(c); ppvL.append(p); npvL.append(n_); f1L.append(f1)  # collect it

    lo_q = (1 - alpha) / 2 * 100
    hi_q = (alpha + (1 - alpha) / 2) * 100

    def q(a):
        a = np.asarray(a)
        return float(np.percentile(a, lo_q)), float(np.percentile(a, hi_q))

    return dict(
        TP_ci=q(tpL), FP_ci=q(fpL), TN_ci=q(tnL), FN_ci=q(fnL),
        Sens_ci=q(sensL), Spec_ci=q(specL), PPV_ci=q(ppvL), NPV_ci=q(npvL), F1_ci=q(f1L)   # add to return dict
    )

# -----------------------------------------
# Bootstrap CI for AUROC & Average Precision
# -----------------------------------------

def bootstrap_ci_auc_ap(y_true, y_prob, n_boot=1000, alpha=0.95, seed=123):
    """Threshold-free bootstrap CIs for AUROC and AUPRC."""
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)
    n = len(y_true)

    aucs=[]; aps=[]
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        yt = y_true[idx]; yp = y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, yp))
        aps.append(average_precision_score(yt, yp))

    lo_q = (1 - alpha) / 2 * 100
    hi_q = (alpha + (1 - alpha) / 2) * 100
    auc_ci = (float(np.percentile(aucs, lo_q)), float(np.percentile(aucs, hi_q))) if aucs else (np.nan, np.nan)
    ap_ci  = (float(np.percentile(aps,  lo_q)), float(np.percentile(aps,  hi_q))) if aps  else (np.nan, np.nan)
    return auc_ci, ap_ci

# -----------------------------------------
# Calibration stats (ECE + slope/intercept)
# -----------------------------------------

def calibration_stats(y_true, y_prob, n_bins=10, strategy="quantile"):
    """
    Compute ECE (bin-weighted abs gap), calibration slope and intercept from
    a logistic regression of y on score.
    """
    y_true = np.asarray(y_true).ravel()
    y_prob = _ensure_1d(y_prob)

    prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=n_bins, strategy=strategy)
    bin_counts = np.histogram(y_prob, bins=n_bins)[0]
    total = np.sum(bin_counts)
    valid = min(len(prob_true), len(prob_pred), len(bin_counts))
    ece = float(np.sum((bin_counts[:valid] / total) * np.abs(prob_true[:valid] - prob_pred[:valid])))

    lr = LogisticRegression(solver="lbfgs")
    lr.fit(y_prob.reshape(-1, 1), y_true)
    slope = float(lr.coef_[0][0])
    intercept = float(lr.intercept_[0])
    return ece, slope, intercept

# ------------------------------------------------------
# Table 4: thresholds for target sensitivities (+ Youden)
# ------------------------------------------------------

def table_thresholds_for_targets(
    y_sel, y_sel_pred,           # set used to select the threshold (val or test)
    y_eval, y_eval_pred,         # set used to evaluate metrics (usually test)
    targets=(0.70, 0.75, 0.80, 0.85, 0.90),
    include_youden=True,
    strategy="closest",          # selection strategy
    rule=">",                    # classification rule for evaluation
    include_interpolated=False   # optionally report probabilistic mix to hit target exactly
) -> pd.DataFrame:
    y_sel_pred  = _ensure_1d(y_sel_pred)
    y_eval_pred = _ensure_1d(y_eval_pred)

    rows = []
    for t in targets:
        thr, sens_sel = find_threshold_for_target_recall(
            y_sel, y_sel_pred, t, strategy=strategy, rule=rule
        )
        tp, fp, tn, fn = counts_at_threshold(y_eval, y_eval_pred, thr, rule=rule)
        sens, spec, ppv, npv, f1 = rates_from_counts(tp, fp, tn, fn)

        row = dict(ThresholdType=f"{t:.2f}", Target=t,
                   Sens=sens, Spec=spec, PPV=ppv, NPV=npv, F1=f1, Thr=thr,
                   Sens_selected=sens_sel)

        if include_interpolated:
            hi, lo, p, r_exp = interpolated_recall_threshold(y_eval, y_eval_pred, t)
            row.update(dict(Interp_thr_hi=hi, Interp_thr_lo=lo, Interp_mix=p, Interp_Sens=r_exp))

        rows.append(row)

    if include_youden:
        thr, _, _ = get_youden_threshold(y_sel, y_sel_pred)
        tp, fp, tn, fn = counts_at_threshold(y_eval, y_eval_pred, thr, rule=rule)
        sens, spec, ppv, npv, f1 = rates_from_counts(tp, fp, tn, fn)
        rows.append(dict(ThresholdType="Youden", Target=np.nan,
                         Sens=sens, Spec=spec, PPV=ppv, NPV=npv, F1=f1, Thr=thr,
                         Sens_selected=np.nan))

    cols = ["ThresholdType","Target","Sens","Spec","PPV","NPV", "F1","Thr","Sens_selected"]
    if include_interpolated:
        cols += ["Interp_thr_hi","Interp_thr_lo","Interp_mix","Interp_Sens"]
    return pd.DataFrame(rows, columns=cols)

# -------------------------------------------------------------------
# Table 5: confusion-matrix counts with 95% CI at a chosen target TPR
# -------------------------------------------------------------------

def table_confusion_counts_with_ci(
    y_val, y_val_pred, y_test, y_test_pred,
    target=0.80, select_on="val",      # "val" or "test"
    n_boot=1000, alpha=0.95, seed=123,
    strategy="closest", rule=">"
) -> pd.DataFrame:
    y_val_pred  = _ensure_1d(y_val_pred)
    y_test_pred = _ensure_1d(y_test_pred)

    if select_on == "val":
        thr, _ = find_threshold_for_target_recall(y_val,  y_val_pred,  target, strategy=strategy, rule=rule)
    else:
        thr, _ = find_threshold_for_target_recall(y_test, y_test_pred, target, strategy=strategy, rule=rule)

    tp, fp, tn, fn = counts_at_threshold(y_test, y_test_pred, thr, rule=rule)
    cis = bootstrap_ci_fixed_threshold(y_test, y_test_pred, thr, n_boot=n_boot, alpha=alpha, seed=seed, rule=rule)

    rows = [
        dict(Metric="TP", Value=tp,  CI_low=int(round(cis["TP_ci"][0])), CI_high=int(round(cis["TP_ci"][1]))),
        dict(Metric="FP", Value=fp,  CI_low=int(round(cis["FP_ci"][0])), CI_high=int(round(cis["FP_ci"][1]))),
        dict(Metric="TN", Value=tn,  CI_low=int(round(cis["TN_ci"][0])), CI_high=int(round(cis["TN_ci"][1]))),
        dict(Metric="FN", Value=fn,  CI_low=int(round(cis["FN_ci"][0])), CI_high=int(round(cis["FN_ci"][1]))),
    ]
    df = pd.DataFrame(rows)
    df.attrs["threshold"] = float(thr)
    df.attrs["selected_on"] = select_on
    df.attrs["target_sensitivity"] = float(target)
    df.attrs["rule"] = rule
    df.attrs["strategy"] = strategy
    return df

# ----------------------------------------------------------------------
# Table 2: performance metrics with CI at chosen target threshold (TPR)
# ----------------------------------------------------------------------

def table_performance_metrics_with_ci(
    y_val, y_val_pred, y_test, y_test_pred,
    target=0.80, select_on="val",      # "val" or "test"
    n_boot=1000, alpha=0.95, seed=123,
    cal_n_bins=10, cal_strategy="quantile",
    strategy="closest", rule=">"
) -> pd.DataFrame:
    y_val_pred  = _ensure_1d(y_val_pred)
    y_test_pred = _ensure_1d(y_test_pred)

    # choose threshold on the requested split
    if select_on == "val":
        thr, _ = find_threshold_for_target_recall(y_val,  y_val_pred,  target, strategy=strategy, rule=rule)
    else:
        thr, _ = find_threshold_for_target_recall(y_test, y_test_pred, target, strategy=strategy, rule=rule)

    # point estimates on TEST
    auc  = roc_auc_score(y_test, y_test_pred)
    ap   = average_precision_score(y_test, y_test_pred)
    tp, fp, tn, fn = counts_at_threshold(y_test, y_test_pred, thr, rule=rule)
    sens, spec, ppv, npv, f1 = rates_from_counts(tp, fp, tn, fn)
    brier = brier_score_loss(y_test, y_test_pred)
    ece, slope, intercept = calibration_stats(y_test, y_test_pred, n_bins=cal_n_bins, strategy=cal_strategy)
    prevalence = float(np.mean(y_test))

    # Confidence intervals
    auc_ci, ap_ci = bootstrap_ci_auc_ap(y_test, y_test_pred, n_boot=n_boot, alpha=alpha, seed=seed)
    cis_fixed = bootstrap_ci_fixed_threshold(y_test, y_test_pred, thr, n_boot=n_boot, alpha=alpha, seed=seed, rule=rule)

    rows = [
        dict(Metric="AUROC (95% CI) ↑",  Point=auc,  CI_low=auc_ci[0], CI_high=auc_ci[1]),
        dict(Metric="AUPRC (95% CI) ↑",  Point=ap,   CI_low=ap_ci[0],  CI_high=ap_ci[1]),
        dict(Metric="Sensitivity (95% CI) ↑", Point=sens, CI_low=cis_fixed["Sens_ci"][0], CI_high=cis_fixed["Sens_ci"][1]),
        dict(Metric="Specificity (95% CI) ↑", Point=spec, CI_low=cis_fixed["Spec_ci"][0], CI_high=cis_fixed["Spec_ci"][1]),
        dict(Metric="PPV (95% CI) ↑",    Point=ppv,  CI_low=cis_fixed["PPV_ci"][0],  CI_high=cis_fixed["PPV_ci"][1]),
        dict(Metric="NPV (95% CI) ↑",    Point=npv,  CI_low=cis_fixed["NPV_ci"][0],  CI_high=cis_fixed["NPV_ci"][1]),
        dict(Metric="F1 Score (95% CI) ↑", Point=f1, CI_low=cis_fixed["F1_ci"][0], CI_high=cis_fixed["F1_ci"][1]),
        dict(Metric="Brier Score ↓",     Point=brier, CI_low=np.nan, CI_high=np.nan),
        dict(Metric="Calibration Slope → 1", Point=slope, CI_low=np.nan, CI_high=np.nan),
        dict(Metric="Calibration Intercept → 0", Point=intercept, CI_low=np.nan, CI_high=np.nan),
        dict(Metric="ECE ↓",             Point=ece, CI_low=np.nan, CI_high=np.nan),
        dict(Metric="Prevalence",        Point=prevalence, CI_low=np.nan, CI_high=np.nan),
    ]
    df = pd.DataFrame(rows, columns=["Metric","Point","CI_low","CI_high"])
    df.attrs["threshold"] = float(thr)
    df.attrs["selected_on"] = select_on
    df.attrs["target_sensitivity"] = float(target)
    df.attrs["rule"] = rule
    df.attrs["strategy"] = strategy
    return df

# ---------------------------------------------------------------------------
# Convenience wrapper: build & save all tables for VAL-selected and TEST-selected
# ---------------------------------------------------------------------------

def build_all_tables_for_model(
    class_name: str,
    y_val, y_val_pred,
    y_test, y_test_pred,
    targets=(0.70, 0.75, 0.80, 0.85, 0.90),
    main_target=0.80,                     # used for Tables 2 & 5
    n_boot=1000, alpha=0.95, seed=123,
    figures_dir="figures",
    # global knobs for consistency
    strategy="closest",
    rule=">",
    cal_n_bins=10,
    cal_strategy="quantile"
):
    """
    Produce 3 CSVs for VAL-selected thresholds and 3 CSVs for TEST-selected thresholds:
      - Table 4 (threshold grid)
      - Table 5 (counts + bootstrap CI at main_target)
      - Table 2 (performance + bootstrap CI at main_target)
    """
    os.makedirs(os.path.join(figures_dir, class_name), exist_ok=True)
    out_dir = os.path.join(figures_dir, class_name)

    # # --- thresholds table (select on VAL) ---
    t4_val = table_thresholds_for_targets(
        y_val, y_val_pred, y_test, y_test_pred,
        targets=targets, include_youden=True, strategy=strategy, rule=rule
    )
    t4_val.to_csv(os.path.join(out_dir, f"table4_thresholds_selectOnVAL_{class_name}.csv"), index=False)

    # --- thresholds table (select on TEST) ---
    t4_test = table_thresholds_for_targets(
        y_test, y_test_pred, y_test, y_test_pred,
        targets=targets, include_youden=True, strategy=strategy, rule=rule
    )
    t4_test.to_csv(os.path.join(out_dir, f"table4_thresholds_selectOnTEST_{class_name}.csv"), index=False)

    # # --- confusion counts (Table 5 style) ---
    t5_val  = table_confusion_counts_with_ci(
        y_val, y_val_pred, y_test, y_test_pred,
        target=main_target, select_on="val",
        n_boot=n_boot, alpha=alpha, seed=seed,
        strategy=strategy, rule=rule
    )
    t5_val.to_csv(os.path.join(out_dir, f"table5_counts_selectOnVAL_target{int(main_target*100)}_{class_name}.csv"), index=False)

    t5_test = table_confusion_counts_with_ci(
        y_val, y_val_pred, y_test, y_test_pred,
        target=main_target, select_on="test",
        n_boot=n_boot, alpha=alpha, seed=seed,
        strategy=strategy, rule=rule
    )
    t5_test.to_csv(os.path.join(out_dir, f"table5_counts_selectOnTEST_target{int(main_target*100)}_{class_name}.csv"), index=False)

    # # --- performance metrics (Table 2 style) ---
    t2_val  = table_performance_metrics_with_ci(
        y_val, y_val_pred, y_test, y_test_pred,
        target=main_target, select_on="val",
        n_boot=n_boot, alpha=alpha, seed=seed,
        cal_n_bins=cal_n_bins, cal_strategy=cal_strategy,
        strategy=strategy, rule=rule
    )
    t2_val.to_csv(os.path.join(out_dir, f"table2_metrics_selectOnVAL_target{int(main_target*100)}_{class_name}.csv"), index=False)

    t2_test = table_performance_metrics_with_ci(
        y_val, y_val_pred, y_test, y_test_pred,
        target=main_target, select_on="test",
        n_boot=n_boot, alpha=alpha, seed=seed,
        cal_n_bins=cal_n_bins, cal_strategy=cal_strategy,
        strategy=strategy, rule=rule
    )
    t2_test.to_csv(os.path.join(out_dir, f"table2_metrics_selectOnTEST_target{int(main_target*100)}_{class_name}.csv"), index=False)

    return dict(
        table4_val=None, table4_test=t4_test,
        table5_val=None, table5_test=t5_test,
        table2_val=None, table2_test=t2_test
    )