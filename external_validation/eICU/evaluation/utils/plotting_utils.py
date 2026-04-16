# utils/plotting_utils.py
# Matplotlib-only plotting from cached precomputations.
from __future__ import annotations
import os
from typing import Dict, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt

# -------- global style defaults (can be overridden via set_plot_defaults) -----
DEFAULTS = dict(
    dpi=600,
    transparent=True,
    title_sep=" - ",
    fonts=dict(title=16, label=16, tick=12, legend=14, shap_label=20, shap_tick=16),
    line_width=3,
    grid=True,
    tight=True
)

def set_plot_defaults(**overrides) -> Dict:
    """
    Override module-level DEFAULTS. Example:
      set_plot_defaults(dpi=300, fonts=dict(title=18, label=16, tick=12, legend=12, shap_tick=8))
    Returns the updated DEFAULTS for convenience.
    """
    global DEFAULTS
    for k, v in overrides.items():
        if k == "fonts" and isinstance(v, dict):
            DEFAULTS["fonts"].update(v)
        else:
            DEFAULTS[k] = v
    return DEFAULTS

# -------- internal helpers ----------------------------------------------------
def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _save(fig, out_png: str, dpi: int, transparent: bool,
          save_pdf: bool = False, pdf_dpi: Optional[int] = None) -> None:
    fig.patch.set_alpha(0.0)          # ensure transparent background in viewers
    fig.set_facecolor("none")
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight", transparent=transparent)
    if save_pdf:
        fig.savefig(out_png.replace(".png", ".pdf"),
                    dpi=(pdf_dpi or dpi),
                    bbox_inches="tight",
                    transparent=transparent)

# -------- ROC -----------------------------------------------------------------
def plot_roc_from_cache(
    class_name: str,
    curves: Dict[str, np.ndarray],
    *,
    out_dir: str = "figures",
    fig_size: Tuple[float, float] = (7, 5),
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    show_random: bool = True,
    show_prevalence: bool = True,
    legend_loc: str = "lower right",
    save_pdf: bool = False
) -> str:
    """
    Plot AUROC using cached fpr/tpr and bootstrap CI if present.
    Returns the path to the saved PNG.
    """
    f = plt.figure(figsize=fig_size)

    fpr = curves["fpr"]
    tpr = curves["tpr"]
    auc = float(curves["auc"][0])
    lo, hi = curves["auc_ci"]
    baseline = float(curves["baseline"][0])  # prevalence

    title = f"AUROC{DEFAULTS['title_sep']}{class_name}"
    label = f"AUC = {auc:.3f}"
    if np.isfinite(lo) and np.isfinite(hi):
        label += f"\n({lo:.3f}, {hi:.3f})"
    if show_prevalence:
        label += f"\n[{baseline*100:.2f}%]"

    if show_random:
        plt.plot([0, 1], [0, 1], "-.", color='black', lw=DEFAULTS["line_width"], label="Random")
    plt.plot(fpr, tpr, lw=DEFAULTS["line_width"], color="blue", label=label)
        
    if xlim:
        plt.xlim(*xlim)
    if ylim:
        plt.ylim(*ylim)

    plt.xlabel("False Positive Rate", fontsize=DEFAULTS["fonts"]["label"])
    plt.ylabel("True Positive Rate", fontsize=DEFAULTS["fonts"]["label"])
    # plt.title(title, fontsize=DEFAULTS["fonts"]["title"])
    plt.legend(loc=legend_loc, fontsize=DEFAULTS["fonts"]["legend"], framealpha=0)
    plt.tick_params(axis="both", labelsize=DEFAULTS["fonts"]["tick"])
    if DEFAULTS["grid"]:
        plt.grid(True)
    if DEFAULTS["tight"]:
        plt.tight_layout()

    outp = os.path.join(out_dir, class_name, f"AUROC_{class_name}.png")
    _ensure_dir(os.path.dirname(outp))
    _save(f, outp, dpi=DEFAULTS["dpi"], transparent=DEFAULTS["transparent"], save_pdf=save_pdf)
    plt.close()
    return outp

# -------- AUPRC ---------------------------------------------------------------
def plot_auprc_from_cache(
    class_name: str,
    curves: Dict[str, np.ndarray],
    *,
    out_dir: str = "figures",
    fig_size: Tuple[float, float] = (7, 5),
    legend_loc: str = "lower left",
    prevalence_label_mode: str = "brackets",  # "brackets" -> "AP 0.83 [0.33%]" | "label" -> "AP 0.83 — Prevalence: 0.33%"
    save_pdf: bool = False
) -> str:
    """
    Plot Precision–Recall with AP and 'no skill' baseline (prevalence).
    Returns the path to the saved PNG.
    """
    f = plt.figure(figsize=fig_size)

    recall = curves["recall"]
    precision = curves["precision"]
    ap = float(curves["ap"][0])
    baseline = float(curves["baseline"][0])  # prevalence

    if prevalence_label_mode == "brackets":
        legend_label = f"AP = {ap:.3f} [{baseline*100:.2f}%]"
    else:
        legend_label = f"AP = {ap:.3f} — Prevalence: {baseline*100:.2f}%"

    plt.plot(recall, precision, lw=DEFAULTS["line_width"], color="black", label=legend_label)
    plt.hlines(baseline, 0, 1, linestyles="--", linewidth=DEFAULTS["line_width"], colors="grey", label="No Skill")
    plt.xlabel("Recall", fontsize=DEFAULTS["fonts"]["label"])
    plt.ylabel("Precision", fontsize=DEFAULTS["fonts"]["label"])
    # plt.title(f"Precision–Recall{DEFAULTS['title_sep']}{class_name}", fontsize=DEFAULTS["fonts"]["title"])
    plt.legend(loc=legend_loc, fontsize=DEFAULTS["fonts"]["legend"], framealpha=0)
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    if DEFAULTS["grid"]:
        plt.grid(True)
    if DEFAULTS["tight"]:
        plt.tight_layout()

    outp = os.path.join(out_dir, class_name, f"AUPRC_{class_name}.png")
    _ensure_dir(os.path.dirname(outp))
    _save(f, outp, dpi=DEFAULTS["dpi"], transparent=DEFAULTS["transparent"], save_pdf=save_pdf)
    plt.close()
    return outp

# -------- Calibration ----------------------------------------------------------
def plot_calibration_from_cache(
    class_name: str,
    curves: Dict[str, np.ndarray],
    *,
    out_dir: str = "figures",
    fig_size: Tuple[float, float] = (6, 5),
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    ticks = [0, 0.004, 0.008, 0.012, 0.016],
    legend_loc: str = "best",
    save_pdf: bool = False
) -> str:
    """
    Plot calibration curve with ECE annotation.
    Returns the path to the saved PNG.
    """
    f = plt.figure(figsize=fig_size)

    pp = curves["prob_pred"]  # mean predicted prob in bin
    pt = curves["prob_true"]  # empirical prob in bin
    ece = float(curves["ece"][0])

    plt.plot(pp, pt, marker="o", linestyle=":", color="red",
             linewidth=DEFAULTS["line_width"], label=f"ECE {ece:.2e}")
    plt.plot([0, 1], [0, 1], color="black", linewidth=DEFAULTS["line_width"])

    maxv = max(pp.max(), pt.max()) if (pp.size and pt.size) else 1.0
    plt.xlim(0, maxv * 1.05)
    plt.ylim(0, maxv * 1.05)
    if xlim:
        plt.xlim(*xlim)
    if ylim:
        plt.ylim(*ylim)

    plt.xticks(ticks)
    plt.yticks(ticks)

    plt.xlabel("Mean predicted probability", fontsize=DEFAULTS["fonts"]["label"])
    plt.ylabel("True probability", fontsize=DEFAULTS["fonts"]["label"])
    # plt.title(f"Calibration{DEFAULTS['title_sep']}{class_name}", fontsize=DEFAULTS["fonts"]["title"])
    plt.legend(loc=legend_loc, fontsize=DEFAULTS["fonts"]["legend"], framealpha=0)
    plt.tick_params(axis="both", labelsize=DEFAULTS["fonts"]["tick"])
    if DEFAULTS["grid"]:
        plt.grid(True)
    if DEFAULTS["tight"]:
        plt.tight_layout()

    outp = os.path.join(out_dir, class_name, f"Calibration_{class_name}.png")
    _ensure_dir(os.path.dirname(outp))
    _save(f, outp, dpi=DEFAULTS["dpi"], transparent=DEFAULTS["transparent"], save_pdf=save_pdf)
    plt.close()
    return outp

# -------- Decision Curve (Net Benefit) ----------------------------------------
def plot_decision_curve_from_cache(
    class_name: str,
    curves: Dict[str, np.ndarray],
    *,
    out_dir: str = "figures",
    fig_size: Tuple[float, float] = (7, 5),
    xlim: Optional[Tuple[float, float]] = None,
    ylim: Optional[Tuple[float, float]] = None,
    legend_loc: str = "best",
    save_pdf: bool = False
) -> str:
    """
    Plot decision curve analysis (net benefit) using cached arrays.
    Returns the path to the saved PNG.
    """
    f = plt.figure(figsize=fig_size)

    thr = curves["dca_thresholds"]
    nb_model = curves["nb_model"]
    nb_all = curves["nb_all"]
    nb_none = curves["nb_none"]
    a_model, a_all, a_none = curves["aunbc"]

    plt.plot(thr, nb_model, linestyle=":", color="black",
             linewidth=DEFAULTS["line_width"], label=f"Model {a_model:.2e}")
    plt.plot(thr, nb_all, linestyle="-.", color='blue', linewidth=DEFAULTS["line_width"], label=f"Refer All {a_all:.2e}")
    plt.plot(thr, nb_none, linestyle="--", color='red', linewidth=DEFAULTS["line_width"], label=f"Refer None {a_none:.2e}")
    plt.axhline(0, color="grey", linewidth=DEFAULTS["line_width"])

    if xlim:
        plt.xlim(*xlim)
    if ylim:
        plt.ylim(*ylim)

    plt.xlabel("Threshold probability (pt)", fontsize=DEFAULTS["fonts"]["label"])
    plt.ylabel("Net Benefit", fontsize=DEFAULTS["fonts"]["label"])
    # plt.title(f"Decision Curve{DEFAULTS['title_sep']}{class_name}", fontsize=DEFAULTS["fonts"]["title"])
    plt.legend(loc=legend_loc, fontsize=DEFAULTS["fonts"]["legend"], framealpha=0)
    plt.tick_params(axis="both", labelsize=DEFAULTS["fonts"]["tick"])
    if DEFAULTS["grid"]:
        plt.grid(True)
    if DEFAULTS["tight"]:
        plt.tight_layout()

    outp = os.path.join(out_dir, class_name, f"DecisionCurve_{class_name}.png")
    _ensure_dir(os.path.dirname(outp))
    _save(f, outp, dpi=DEFAULTS["dpi"], transparent=DEFAULTS["transparent"], save_pdf=save_pdf)
    plt.close()
    return outp

# -------- SHAP beeswarm from cache --------------------------------------------
def plot_shap_beeswarm_from_cache(
    class_name: str,
    shap_explanation,              # shap.Explanation constructed from cache
    *,
    out_dir: str = "figures",
    fig_size: Tuple[float, float] = (6, 4),
    max_display: int = 30,
    save_pdf: bool = False
) -> str:
    """
    Plot a SHAP beeswarm from a cached shap.Explanation.
    Returns the path to the saved PNG.
    """
    import shap

    f = plt.figure(figsize=fig_size)
    shap.plots.beeswarm(shap_explanation, show=False, max_display=max_display)
    
    ax = plt.gca()
    ax.tick_params(axis="y", labelsize=DEFAULTS["fonts"]["shap_tick"])
    ax.tick_params(axis="x", labelsize=DEFAULTS["fonts"]["shap_tick"])
    
    ax.set_xlabel(ax.get_xlabel(), fontsize=DEFAULTS["fonts"]["shap_label"])
    ax.set_ylabel(ax.get_ylabel(), fontsize=DEFAULTS["fonts"]["shap_label"])

    cbar = f.axes[-1]
    cbar.tick_params(labelsize=DEFAULTS["fonts"]["shap_tick"])
    cbar.set_ylabel(cbar.get_ylabel(), fontsize=DEFAULTS["fonts"]["shap_label"])

    # plt.title(f"SHAP Feature Importance{DEFAULTS['title_sep']}{class_name}",
    #           fontsize=DEFAULTS["fonts"]["title"])
    if DEFAULTS["tight"]:
        plt.tight_layout()

    outp = os.path.join(out_dir, class_name, f"SHAP_{class_name}.png")
    _ensure_dir(os.path.dirname(outp))
    _save(f, outp, dpi=DEFAULTS["dpi"], transparent=DEFAULTS["transparent"], save_pdf=save_pdf)
    plt.close()
    return outp