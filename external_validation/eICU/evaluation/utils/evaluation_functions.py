import sys
import xgboost as xgb
import pandas as pd
import numpy as np
import joblib
import os
import logging
from sklearn.metrics import roc_auc_score, roc_curve, precision_recall_curve, average_precision_score, confusion_matrix, recall_score, brier_score_loss
from scipy.integrate import trapezoid
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
import plotly.graph_objs as go
import plotly.io as pio

import shap
from shap import TreeExplainer
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from scipy.integrate import trapezoid
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from sqlalchemy import create_engine



sys.path.append("..")
DATABASE_URI = "postgresql+psycopg2://USER@localhost:5433/eicu"
engine = create_engine(DATABASE_URI, future=True)

CALIBRATED_MODELS_DIR = "../models/calibrated"
FIGURES_DIR = "figures"

## NEW


def load_and_prepare_data_xgb(table_name: str):
    """
    Loads and prepares validation and test data from the database.

    Args:
        table_name (str): Name of the table to load from (in schema public).

    Returns:
        x_val, y_val, x_test, y_test, feature_cols
    """
    engine = create_engine(DATABASE_URI, future=True)

    df = pd.read_sql(f"""
        SELECT * FROM public.{table_name}
        WHERE split IN ('val', 'test')
    """, engine)

    drop_cols = ["patienthealthsystemstayid", "patientunitstayid", "context_start_offset_min", "context_end_offset_min", "target_start_offset_min", "target_end_offset"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    df["label"] = df["positive_event"].astype(int)

    excluded_cols = {"positive_event", "positive_sample", "split", "label"}

    if "admissionweight_bin" in df.columns:
        print("Found admissionweight_bin")
        df = df.rename(columns={"admissionweight_bin": "weight_bin"})
    if "admissionheight_bin" in df.columns:
        print("FOund admissionheight_bin")
        df = df.rename(columns={"admissionheight_bin": "height_bin"})
   

    feature_cols = [c for c in df.columns if c not in excluded_cols]

    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]

    x_val = val_df[feature_cols]
    y_val = val_df["label"]
    x_test = test_df[feature_cols]
    y_test = test_df["label"]

    return x_val, y_val, x_test, y_test, feature_cols


def load_and_prepare_data_baseline():
    """
    Load the last MAP value (last_map) and binary event label from the database.
    Splits: train / val / test
    """
    engine = create_engine(DATABASE_URI, future=True)
    query = """
    SELECT
    mw.patienthealthsystemstayid,
    split_part(
        split_part(last_map_elem.elem, '|', 2),
        ':',
        2
    )::float AS last_map,
    mw.positive_event,
    sm.split
FROM public.mix_windows mw
LEFT JOIN LATERAL (
    SELECT elem
    FROM unnest(string_to_array(mw.map_values, ';')) AS elem
    ORDER BY split_part(split_part(elem, '|', 1), ':', 2)::float DESC
    LIMIT 1
) last_map_elem ON TRUE
JOIN public.split_all_admissions sm
    ON mw.patienthealthsystemstayid = sm.patienthealthsystemstayid
WHERE sm.split IN ('train', 'val', 'test');
    """
    df = pd.read_sql(query, engine)
    df["label"] = df["positive_event"].astype(int)

    # Create val / test datasets

    X_val = df[df["split"] == "val"][["last_map"]]
    y_val = df[df["split"] == "val"]["label"]
    
    X_test = df[df["split"] == "test"][["last_map"]]
    y_test = df[df["split"] == "test"]["label"]

    return X_val, y_val, X_test, y_test, ["last"]


def plot_precision_recall_curve(y_true, y_prob, class_name: str, max_points: int = None):
    logging.info(f"📈 Running plot_precision_recall_curve (XGBoost, HTML-only)")

    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    average_precision = average_precision_score(y_true, y_prob)
    baseline = np.sum(y_true) / len(y_true)
    thresholds_full = np.append(thresholds, np.nan)

    if max_points and len(recall) > max_points:
        step = max(1, len(recall) // max_points)
        precision = precision[::step]
        recall = recall[::step]
        thresholds_full = thresholds_full[::step]
        logging.info(f"🔧 Reduced PR curve to {len(recall)} points (step={step})")

    trace_model = go.Scatter(
        x=recall,
        y=precision,
        mode='lines',
        name=f'Model (AP = {average_precision:.3f})',
        customdata=np.stack((recall, precision, thresholds_full), axis=-1),
        hovertemplate='Recall: %{customdata[0]:.3f}<br>Precision: %{customdata[1]:.3f}<br>Threshold: %{customdata[2]:.3f}<extra></extra>',
        line=dict(color='black')
    )

    trace_baseline = go.Scatter(
        x=[0, 1],
        y=[baseline, baseline],
        mode='lines',
        name=f'No Skill (Pos rate = {baseline:.3f})',
        line=dict(color='red', dash='dash'),
        hoverinfo='skip'
    )

    fig = go.Figure(data=[trace_model, trace_baseline])
    fig.update_layout(
        title=f'Precision-Recall Curve: {class_name}',
        xaxis_title='Recall',
        yaxis_title='Precision',
        template='simple_white',
        legend=dict(x=0.98, y=0.98, xanchor='right', yanchor='top')
    )

    os.makedirs(FIGURES_DIR, exist_ok=True)
    os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
    html_path = os.path.join(f"{FIGURES_DIR}/{class_name}", f"precision_recall_{class_name}.html")
    pio.write_html(fig, file=html_path, auto_open=False)
    logging.info(f"💾 Saved PR curve to {html_path}")

    fig.show()


def plot_roc_with_bootstrap_plotly(
    y_true, y_pred_probs, class_name: str, alpha=0.95, iterations=1000, max_points=1000
):
    logging.info(f"📈 Running plot_roc_with_bootstrap_plotly")
    try:
        y_true = np.asarray(y_true)
        y_pred_probs = np.asarray(y_pred_probs)

        base_auc = roc_auc_score(y_true, y_pred_probs)
        bootstrap_aucs = []

        for _ in range(iterations):
            idx = np.random.choice(len(y_true), len(y_true), replace=True)
            if len(np.unique(y_true[idx])) > 1:
                auc_sample = roc_auc_score(y_true[idx], y_pred_probs[idx])
                bootstrap_aucs.append(auc_sample)

        bootstrap_aucs = np.array(bootstrap_aucs)
        auc_diff = bootstrap_aucs - base_auc
        low_auc = base_auc + np.percentile(auc_diff, ((1.0 - alpha) / 2.0) * 100)
        high_auc = base_auc + np.percentile(auc_diff, (alpha + ((1.0 - alpha) / 2.0)) * 100)

        fpr, tpr, thresholds = roc_curve(y_true, y_pred_probs)

        # Pad thresholds to align with fpr/tpr shape (add NaN to match shape)
        thresholds = np.append(thresholds, np.nan)

        # Optional: Reduce number of points
        if len(fpr) > max_points:
            step = max(1, len(fpr) // max_points)
            fpr = fpr[::step]
            tpr = tpr[::step]
            thresholds = thresholds[::step]

        prevalence = round(y_true.sum() / len(y_true) * 100, 2)
        ci_label = f"AUC = {base_auc:.3f} ({low_auc:.3f}, {high_auc:.3f}) — Prevalence: {prevalence}%"

        trace_model = go.Scatter(
            x=fpr,
            y=tpr,
            mode='lines',
            name=ci_label,
            customdata=np.stack((fpr, tpr, thresholds), axis=-1),
            hovertemplate=(
                'FPR: %{customdata[0]:.3f}<br>' +
                'TPR: %{customdata[1]:.3f}<br>' +
                'Threshold: %{customdata[2]:.3f}<extra></extra>'
            ),
            line=dict(width=3, color='black')
        )

        trace_random = go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode='lines',
            name='Random classifier',
            line=dict(dash='dash', color='gray'),
            hoverinfo='skip'
        )

        fig = go.Figure(data=[trace_model, trace_random])
        fig.update_layout(
            title=f"ROC Curve — {class_name}",
            xaxis_title='False Positive Rate',
            yaxis_title='True Positive Rate',
            template='simple_white',
            width=800,
            height=600,
            legend=dict(x=0.02, y=0.02)
        )

        os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
        html_path = os.path.join(f"{FIGURES_DIR}/{class_name}", f"AUROC_{class_name}_plotly.html")
        fig.write_html(html_path)
        logging.info(f"💾 Saved interactive ROC curve to {html_path}")

        fig.show()

    except Exception as e:
        logging.error(f"❌ Error while plotting ROC: {e}")


def plot_roc_with_bootstrap(y_true, y_pred_probs, class_name: str, alpha=0.95, iterations=1000):
    logging.info(f" Running plot_roc_with_bootstrap")
    try:
        # Convert to NumPy arrays to avoid index issues
        y_true = np.asarray(y_true)
        y_pred_probs = np.asarray(y_pred_probs)

        base_auc = roc_auc_score(y_true, y_pred_probs)
        bootstrap_aucs = []

        for _ in range(iterations):
            idx = np.random.choice(len(y_true), len(y_true), replace=True)
            if len(np.unique(y_true[idx])) > 1:
                auc_sample = roc_auc_score(y_true[idx], y_pred_probs[idx])
                bootstrap_aucs.append(auc_sample)

        bootstrap_aucs = np.array(bootstrap_aucs)
        auc_diff = bootstrap_aucs - base_auc
        low_auc = base_auc + np.percentile(auc_diff, ((1.0 - alpha) / 2.0) * 100)
        high_auc = base_auc + np.percentile(auc_diff, (alpha + ((1.0 - alpha) / 2.0)) * 100)

        prevalence = y_true.sum() / len(y_true) * 100
        prevalence = round(prevalence, 2)

        fpr, tpr, _ = roc_curve(y_true, y_pred_probs)

        fig = plt.figure(figsize=(8, 6))
        logging.info("Figure created.")
        cmap = plt.get_cmap("RdBu_r")
        norm = Normalize(vmin=0, vmax=1)
        sm = ScalarMappable(norm=norm, cmap=cmap)
        plt.plot(fpr, tpr, color=sm.to_rgba(0.2), lw=3,
                 label=f'AUC = {base_auc:.3f} ({low_auc:.3f}, {high_auc:.3f}) — Prevalence = {prevalence}%')
        plt.plot([0, 1], [0, 1], 'k-.', label='Random classifier', lw=3)
        plt.xlabel('False Positive Rate', fontsize=16)
        plt.ylabel('True Positive Rate', fontsize=16)
        plt.title(f'AUROC – {class_name}', fontsize=16)
        plt.legend(loc='lower right', fontsize=16, framealpha=0)
        plt.tick_params(axis='both', labelsize=12)
        plt.tight_layout()
        plt.grid(True)
        fig.patch.set_alpha(0.0)
        fig.set_facecolor('none')
        plt.savefig(f'{FIGURES_DIR}/{class_name}/AUROC_{class_name}.png', dpi=600, transparent=True)
        logging.info("Figure saved.")
        # plt.show()
        plt.close()
    except Exception as e:
        logging.error(f"❌ Error while plotting ROC: {e}")
        
        
def plot_calibration(y_test, y_probs_test, class_name: str, ylim=(0, 0.015), xlim=(0, 0.015)):
    # Calibration curve and ECE
    prob_true, prob_pred = calibration_curve(y_test, y_probs_test, n_bins=10, strategy='quantile')
    bin_counts = np.histogram(y_probs_test, bins=10)[0]
    total = np.sum(bin_counts)
    valid_bins = min(len(prob_true), len(prob_pred), len(bin_counts))
    ece = np.sum((bin_counts[:valid_bins] / total) * np.abs(prob_true[:valid_bins] - prob_pred[:valid_bins]))

    # Plot
    fig = plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, marker='o', linestyle=':', label=f'Calibration error {ece:.2e}', color='red', linewidth=3)
    plt.plot([0, 1], [0, 1], color='black', linewidth=3)
    max_val = max(prob_pred.max(), prob_true.max())
    plt.xlim(0, max_val * 1.05)
    plt.ylim(0, max_val * 1.05)
    plt.xlabel('Mean predicted probability', fontsize=16)
    plt.ylabel('True probability', fontsize=16)
    plt.title(f"Calibration – {class_name}", fontsize=16)
    plt.legend(fontsize=16, framealpha=0)
    plt.grid(True)
    plt.tight_layout()
    plt.tick_params(axis='both', labelsize=12)
    fig.patch.set_alpha(0.0)
    fig.set_facecolor('none')
    
    plt.ylim(*ylim)
    plt.xlim(*xlim)

    logging.info(f"💾 Saving calibration to: {FIGURES_DIR}")
    os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
    plt.savefig(f"{FIGURES_DIR}/{class_name}/calibration_{class_name}.png", dpi=600, transparent=True)
    # plt.show()
    plt.close()
    
    return ece
    

def compute_net_benefit(y_true, y_prob, thresholds):
    N = len(y_true)
    net_benefits = []
    for pt in thresholds:
        y_pred = y_prob >= pt
        TP = np.sum((y_true == 1) & (y_pred == 1))
        FP = np.sum((y_true == 0) & (y_pred == 1))
        net_benefit = (TP / N) - (FP / N) * (pt / (1 - pt))
        net_benefits.append(net_benefit)
    return net_benefits

def plot_net_benefit(y_true, y_prob, class_name: str, ylim=(0, 0.0023), xlim=(0, 0.06)):
    logging.info(f" Running plot_net_benefit")
    thresholds = np.linspace(0, y_prob.max()+0.1, 100)
    nb_model = compute_net_benefit(y_true, y_prob, thresholds)
    nb_all = compute_net_benefit(y_true, np.ones_like(y_prob), thresholds)
    nb_none = compute_net_benefit(y_true, np.zeros_like(y_prob), thresholds)

    nb_model = gaussian_filter1d(nb_model, sigma=1)
    nb_all = gaussian_filter1d(nb_all, sigma=1)
    nb_none = gaussian_filter1d(nb_none, sigma=1)

    aunbc_model = trapezoid(nb_model, thresholds)
    aunbc_all = trapezoid(nb_all, thresholds)
    aunbc_none = trapezoid(nb_none, thresholds)

    fig = plt.figure(figsize=(8, 6))
    plt.plot(thresholds, nb_model, label=f"Model {aunbc_model:.2e}", linestyle=':', color='black', linewidth=3)
    plt.plot(thresholds, nb_all, label=f"Refer All {aunbc_all:.2e}", linestyle='-.', color='blue', linewidth=3)
    plt.plot(thresholds, nb_none, label=f"Refer None {aunbc_none:.2e}", linestyle='--', color='red', linewidth=3)
    plt.axhline(0, color='grey', linewidth=3)

    # nb_model = np.array(nb_model)
    # idx_neg = np.where(nb_model < 0)[0]
    # y_min = nb_model[idx_neg[1]] if len(idx_neg) >= 2 else (nb_model[idx_neg[0]] if len(idx_neg) == 1 else -0.0001)
    # max_val = max(np.max(nb_model), np.max(nb_all), np.max(nb_none))
    # plt.ylim(y_min, max_val)

    # idx_x = np.where(nb_model <= 0)[0]
    # x_max = thresholds[idx_x[0]] if len(idx_x) > 0 else thresholds[-1]
    # plt.xlim(thresholds[0], x_max)
    
    plt.ylim(*ylim)
    plt.xlim(*xlim)

    plt.xlabel("Threshold Probability (pt)", fontsize=16)
    plt.ylabel("Net Benefit", fontsize=16)
    plt.title(f"Net Benefit – {class_name}", fontsize=16)
    plt.legend(fontsize=16, framealpha=0)
    plt.grid(True)
    plt.tight_layout()
    plt.tick_params(axis='both', labelsize=12)
    fig.patch.set_alpha(0.0)
    fig.set_facecolor('none')
    logging.info(f"💾 Saving net benefit to: {FIGURES_DIR}")
    os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
    plt.savefig(f"{FIGURES_DIR}/{class_name}/net_benefit_{class_name}.png", dpi=600, transparent=True)
    # plt.show()
    plt.close()
    

def plot_shap_summary(model: xgb.XGBClassifier, X: pd.DataFrame, class_name: str, n_samples=None, max_display=47):
    logging.info("Running optimized SHAP summary plot")

    if n_samples is not None:
        X_sample = X.sample(n=n_samples, random_state=42)
    else: 
        X_sample = X
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X_sample)

    fig, ax = plt.subplots(figsize=(6, 4))
    shap.plots.beeswarm(shap_values, show=False, max_display=max_display)
    plt.title(f'SHAP Feature Importance – {class_name}', fontsize=16)
    plt.tight_layout()

    os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
    plt.savefig(f'{FIGURES_DIR}/{class_name}/shap_{class_name}.png', dpi=300, transparent=True)
    # plt.show()
    plt.close()
    
    
def plot_confusion_matrix(y_true, y_pred_probs, class_name: str, threshold: float = None,
                          save_path: str = None, show: bool = False, cmap: str = "viridis"):
    """
    Plots a confusion matrix with absolute counts and row-wise percentages.
    """
    # Youden's J threshold if none provided
    if threshold is None:
        fpr, tpr, thresholds = roc_curve(y_true, y_pred_probs)
        threshold = thresholds[np.argmax(tpr - fpr)]

    # Apply threshold
    y_pred = (y_pred_probs > threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    specificity = tn / (tn + fp)
    sensitivity = tp / (tp + fn)
    print(f"Sensitivity: {sensitivity:.3f}")
    print(f"Specificity: {specificity:.3f}")
    

    # Percentages row-wise
    row_sums = cm.sum(axis=1, keepdims=True)
    perc = cm / row_sums * 100

    # Plot
    fig, ax = plt.subplots(figsize=(6, 6))
    im = ax.imshow(cm, cmap=cmap, vmin=0, vmax=cm.max())

    # Colorbar (same height as image)
    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    # Ticks & labels
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")

    # Text in each cell
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            count = format(cm[i, j], ',')
            percent = f"{perc[i, j]:.1f}%"
            full_text = f"{count}\n({percent})"

            # Text color based on background
            color = "white" if im.norm(cm[i, j]) < 0.5 else "black"
            ax.text(j, i, full_text, ha="center", va="center", color=color, fontsize=10)

    plt.title(
        f"Confusion Matrix – {class_name}\n"
        f"Sens = {sensitivity:.3f} | Spec = {specificity:.3f} | Thr = {threshold:.4f}",
        fontsize=14
    )

    # Final layout
    fig.tight_layout()

    # Save
    if save_path is None:
        os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
        save_path = f"{FIGURES_DIR}/{class_name}/conf_matrix_{class_name}.png"

    plt.savefig(save_path, dpi=300, bbox_inches='tight')

    plt.close()
        
    return sensitivity, specificity
        
        
def find_threshold_for_target_recall(y_true, y_probs, target_recall):
    fpr, tpr, thresholds = roc_curve(y_true, y_probs)

    for t, r in zip(thresholds, tpr):
        if r >= target_recall:
            return t
    raise ValueError(f"Target recall {target_recall:.3f} is not achievable.")


def evaluate_thresholds_by_target_sensitivity(
    target_sensitivitys,
    y_val,
    y_val_pred,
    y_test,
    y_test_pred,
    class_name,
    show_plots=True
):
    thresholds = []
    sensitivitys = []
    specificitys = []

    for target_recall in target_sensitivitys:
        threshold = threshold_for_recall_from_roc(y_val, y_val_pred, target_recall=target_recall)
        thresholds.append(threshold)

        class_dir = os.path.join(FIGURES_DIR, class_name)
        os.makedirs(class_dir, exist_ok=True)

        save_path = os.path.join(class_dir, f"conf_matrix_{class_name}_recall_{int(target_recall * 100)}.png")
        sensitivity, specificity = plot_confusion_matrix(
            y_true=y_test,
            y_pred_probs=y_test_pred,
            class_name=class_name,
            threshold=threshold,
            show=show_plots,
            save_path=save_path
        )

        sensitivitys.append(sensitivity)
        specificitys.append(specificity)

    threshold_table = pd.DataFrame({
        "target_sensitivity (val)": target_sensitivitys,
        "threshold": thresholds,
        "sensitivity": sensitivitys,
        "specificity": specificitys
    })

    return threshold_table, thresholds, sensitivitys, specificitys




def get_optimal_threshold(y_true, y_scores):
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    distances = np.sqrt((fpr)**2 + (1 - tpr)**2)
    best_idx = np.argmin(distances)
    return thresholds[best_idx], fpr[best_idx], tpr[best_idx]


def get_youden_threshold(y_true, y_scores):
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    youden_j = tpr - fpr
    best_idx = np.argmax(youden_j)
    return thresholds[best_idx], fpr[best_idx], tpr[best_idx]



def evaluate_full_model(
    uncalibrated_model,
    X_test,
    y_val,
    y_val_pred,
    y_test,
    y_test_pred,
    class_name,
    target_sensitivitys=[0.7, 0.75, 0.8, 0.85, 0.9],
    shap_sample_size=None
):
    os.makedirs(f"{FIGURES_DIR}/{class_name}", exist_ok=True)
    logging.info(f"📂 Output directory created: {FIGURES_DIR}/{class_name}")

    # # 1. Core plots
    # logging.info("📊 Generating ROC (plotly)...")
    # plot_roc_with_bootstrap_plotly(y_test, y_test_pred, class_name)

    logging.info("📊 Generating ROC (matplotlib)...")
    plot_roc_with_bootstrap(y_test, y_test_pred, class_name)

    # logging.info("📊 Generating Precision-Recall curve...")
    # plot_precision_recall_curve(y_test, y_test_pred, class_name)

    logging.info("📊 Generating Calibration plot...")
    ece = plot_calibration(y_test, y_test_pred, class_name)

    logging.info("📊 Generating Net Benefit plot...")
    plot_net_benefit(y_test, y_test_pred, class_name)

    # 2. SHAP summary
    logging.info("🧠 Computing SHAP values (this may take time)...")
    X_sample = X_test.sample(n=shap_sample_size, random_state=42) if shap_sample_size else X_test
    explainer = TreeExplainer(uncalibrated_model)
    shap_values = explainer(X_sample)
    plot_shap_summary(uncalibrated_model, X_test, class_name, n_samples=shap_sample_size)

    shap_mean = np.abs(shap_values.values).mean(0)
    top_features = X_sample.columns[np.argsort(shap_mean)[-5:][::-1]].tolist()
    logging.info("✅ SHAP summary done.")

    # 3. Youden threshold (from val)
    youden_threshold, _, _ = get_youden_threshold(y_val, y_val_pred)
    y_pred_youden = (y_test_pred >= youden_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred_youden).ravel()
    youden_sens = tp / (tp + fn)
    youden_spec = tn / (tn + fp)
    logging.info(f"✅ Youden threshold = {youden_threshold:.4f} (sensitivity={youden_sens:.3f}, specificity={youden_spec:.3f})")

    # 4. Thresholds from val @ target sensitivity
    sens_list, spec_list, thresholds_list = [], [], []
    for target in target_sensitivitys:
        logging.info(f"🔍 Searching threshold for target sensitivity: {target:.2f}")
        threshold = find_threshold_for_target_recall(y_val, y_val_pred, target)
        thresholds_list.append(threshold)
        y_pred = (y_test_pred >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        sens = tp / (tp + fn)
        spec = tn / (tn + fp)
        sens_list.append(sens)
        spec_list.append(spec)

        logging.info(f"✅ Threshold = {threshold:.4f} | Sensitivity = {sens:.3f}, Specificity = {spec:.3f}")
        plot_confusion_matrix(y_test, y_test_pred, class_name, threshold=threshold,
                              save_path=f"{FIGURES_DIR}/{class_name}/conf_matrix_{class_name}_recall_{int(target * 100)}.png")

    # 5. Metrics table
    logging.info("🧮 Calculating calibration and final metrics...")
    logreg = LogisticRegression(solver='lbfgs')
    logreg.fit(y_test_pred.reshape(-1, 1), y_test)

    metrics = {
        "AUROC": roc_auc_score(y_test, y_test_pred),
        "AUPRC": average_precision_score(y_test, y_test_pred),
        "Brier Score": brier_score_loss(y_test, y_test_pred),
        "Calibration Slope": logreg.coef_[0][0],
        "Calibration Intercept": logreg.intercept_[0],
        "ECE": ece,
        "Top 5 SHAP Features": ", ".join(top_features),
        "Sens/Spec/Thresh (Youden)": f"{youden_sens:} / {youden_spec:} / {youden_threshold}",
    }

    base_metrics_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
    
    threshold_rows = []
    for i, target in enumerate(target_sensitivitys):
        metric_label = f"Sens/Spec/Thresh ({target:.2f})"
        value_str = f"{sens_list[i]} / {spec_list[i]} / {thresholds_list[i]}"
        threshold_rows.append((metric_label, value_str))
    thresholds_df = pd.DataFrame(threshold_rows, columns=["Metric", "Value"])

    full_df = pd.concat([base_metrics_df, thresholds_df], ignore_index=True)

    save_path = os.path.join(FIGURES_DIR, class_name, f"performance_metrics_{class_name}.csv")
    full_df.to_csv(save_path, index=False)
    logging.info(f"📁 Saved metrics to CSV: {save_path}")

    return full_df

def load_and_evaluate_model(model_name: str, table_name: str, class_name: str, drop_treatment_given: bool = False, drop_only_2_values: bool = False):
    logging.info(f"📥 Starting evaluation for model: {model_name} ({class_name})")
    
    x_val, y_val, x_test, y_test, feature_cols = load_and_prepare_data_xgb(
        table_name=table_name,
        drop_treatment_given=drop_treatment_given,
        drop_only_2_values=drop_only_2_values
    )

    calibrated_model = joblib.load(os.path.join(CALIBRATED_MODELS_DIR, f"{model_name}.pkl"))

    y_val_pred = calibrated_model.predict_proba(x_val)
    y_test_pred = calibrated_model.predict_proba(x_test)

    df_metrics = evaluate_full_model(
        uncalibrated_model=calibrated_model.booster,
        X_test=x_test,
        y_val=y_val,
        y_val_pred=y_val_pred,
        y_test=y_test,
        y_test_pred=y_test_pred,
        class_name=class_name
    )

    return df_metrics