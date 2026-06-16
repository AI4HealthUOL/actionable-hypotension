"""
Sliding Window Methodology Visualization
Shows: 1 intro metadata frame + 3 window hops animated as MP4
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.gridspec import GridSpec
import imageio.v2 as iio
import tempfile
from pathlib import Path

# ─── Fonts & Style ────────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# ─── COLOR PALETTE ────────────────────────────────────────────────────────────
BG        = "#0d1117"
PANEL_BG  = "#161b22"
BORDER    = "#30363d"
TEXT_MAIN = "#e6edf3"
TEXT_MUTED= "#8b949e"
ACCENT    = "#58a6ff"        # blue highlight
GREEN     = "#3fb950"
RED       = "#ff7b72"
ORANGE    = "#f0883e"
PURPLE    = "#bc8cff"
TEAL      = "#79c0ff"
GOLD      = "#e3b341"

CAT_COLORS = {
    "Kristalloide": "#4fc3f7",
    "Elektrolyte":  "#ce93d8",
    "Antibiotika":  "#a5d6a7",
}

# ─── FAKE DATA ────────────────────────────────────────────────────────────────
np.random.seed(42)
N_HOURS = 24
TIME = np.linspace(0, N_HOURS, 200)

# MAP: baseline ~75, dips around hours 8–10 and 18–20
def make_map(t):
    base = 75 + 8 * np.sin(t * 0.3) - 3 * np.sin(t * 1.1)
    dip1 = -25 * np.exp(-0.5 * ((t - 9) / 0.8) ** 2)
    dip2 = -18 * np.exp(-0.5 * ((t - 19) / 1.0) ** 2)
    noise = np.random.normal(0, 2, len(t))
    return np.clip(base + dip1 + dip2 + noise, 35, 130)

MAP_VALUES = make_map(TIME)

# Medication given (0/1) sampled on hourly grid
MED_TIME = np.arange(0, N_HOURS + 0.5, 0.5)  # every 30 min
rng = np.random.default_rng(7)
MEDS = {
    "Kristalloide": (rng.random(len(MED_TIME)) < 0.35).astype(int),
    "Elektrolyte":  (rng.random(len(MED_TIME)) < 0.20).astype(int),
    "Antibiotika":  (rng.random(len(MED_TIME)) < 0.12).astype(int),
}

# Ground-truth catecholamine event at hour 19–21
GT_START = 19.0
GT_END   = 21.0

# Predictions: model fires at hours 17, 17.5, 18 -> target window 19–21
PREDICTIONS = [
    {"context_end": 17.0, "target_start": 19.0, "target_end": 21.0},
    {"context_end": 17.5, "target_start": 19.5, "target_end": 21.5},
    {"context_end": 18.0, "target_start": 19.0, "target_end": 21.0},
]

# Patient metadata
PATIENT = {
    "id": "ICU-202300",
    "gender": "Male",
    "age": 67,
    "ethnicity": "White",
    "height_cm": 178,
    "weight_kg": 84,
    "comorbidities": {
        "Obesity":        False,
        "Hypertension":   True,
        "Diabetes":       True,
        "Kidney Disease": False,
        "Lung Disease":   True,
        "Heart Disease":  True,
    }
}

BMI = PATIENT["weight_kg"] / (PATIENT["height_cm"] / 100) ** 2

# ─── Window hop positions (center of 2h window) ───────────────────────────────
WINDOW_SIZE = 2.0   # hours
HOP_CENTERS = [6.0, 12.0, 18.0]   # where the window is centered

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def set_dark_bg(fig, axes_list):
    fig.patch.set_facecolor(BG)
    for ax in axes_list:
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT_MUTED, labelsize=9)
        ax.xaxis.label.set_color(TEXT_MUTED)
        ax.yaxis.label.set_color(TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.title.set_color(TEXT_MAIN)

def draw_window_highlight(ax, center, size, ymin, ymax, label=True, alpha=0.15):
    """Draw the rolling 2h context window."""
    lo = center - size / 2
    hi = center + size / 2
    ax.axvspan(lo, hi, ymin=0, ymax=1, color=ACCENT, alpha=alpha, zorder=0)
    ax.axvline(lo, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    ax.axvline(hi, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    if label:
        ax.annotate("", xy=(hi, ymax * 0.92), xytext=(lo, ymax * 0.92),
                    arrowprops=dict(arrowstyle="<->", color=ACCENT, lw=1.4))
        ax.text((lo + hi) / 2, ymax * 0.96, "2h context", ha="center",
                fontsize=8, color=ACCENT, fontweight="bold")

def draw_target_arrow(ax, context_end, target_start, target_end, y, color=ORANGE, alpha=0.8):
    """Arrow from context_end → target window."""
    ax.annotate(
        "", xy=(target_start, y), xytext=(context_end, y),
        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5,
                        connectionstyle="arc3,rad=-0.25"),
        zorder=8
    )
    ax.axvspan(target_start, target_end, ymin=0, ymax=1,
               color=color, alpha=0.18, zorder=1)

# ═══════════════════════════════════════════════════════════════════════════════
#  FRAME 1 – METADATA / INTRO SLIDE
# ═══════════════════════════════════════════════════════════════════════════════

def make_metadata_frame(save_path):
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    gs = GridSpec(1, 2, figure=fig, left=0.04, right=0.96,
                  top=0.90, bottom=0.08, wspace=0.06)

    ax_left  = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    ax_left.set_facecolor(PANEL_BG);  ax_right.set_facecolor(PANEL_BG)
    for ax in (ax_left, ax_right):
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    for spine in ax_left.spines.values():  spine.set_edgecolor(BORDER)
    for spine in ax_right.spines.values(): spine.set_edgecolor(BORDER)

    # ── title ──
    fig.text(0.5, 0.96, "Sliding Context Window — Patient Overview",
             ha="center", va="top", fontsize=18, fontweight="bold", color=TEXT_MAIN)
    fig.text(0.5, 0.91, f"ICU Stay: {PATIENT['id']}",
             ha="center", va="top", fontsize=12, color=TEXT_MUTED)

    # ── LEFT: Demographics ──
    ax_left.text(0.5, 0.97, "Demographics", ha="center", va="top",
                 fontsize=14, fontweight="bold", color=ACCENT)

    demo_rows = [
        ("Gender",    PATIENT["gender"]),
        ("Age",       f"{PATIENT['age']} yrs"),
        ("Ethnicity", PATIENT["ethnicity"]),
        ("Height",    f"{PATIENT['height_cm']} cm"),
        ("Weight",    f"{PATIENT['weight_kg']} kg"),
        ("BMI",       f"{BMI:.1f}"),
    ]
    y = 0.87
    for label, val in demo_rows:
        ax_left.text(0.12, y, label, fontsize=12, color=TEXT_MUTED, va="top")
        ax_left.text(0.88, y, val,   fontsize=12, color=TEXT_MAIN,  va="top", ha="right", fontweight="bold")
        ax_left.axhline(y - 0.005, xmin=0.1, xmax=0.9, color=BORDER, lw=0.6)
        y -= 0.12

    # ── RIGHT: Comorbidities ──
    ax_right.text(0.5, 0.97, "Comorbidities", ha="center", va="top",
                  fontsize=14, fontweight="bold", color=ACCENT)

    items = list(PATIENT["comorbidities"].items())
    cols = 2
    rows = (len(items) + cols - 1) // cols
    box_w, box_h = 0.40, 0.11
    xs = [0.05, 0.53]
    ys = np.linspace(0.84, 0.18, rows)

    for idx, (name, present) in enumerate(items):
        r = idx // cols; c = idx % cols
        bx, by = xs[c], ys[r]
        fc = "#2d1f1f" if present else "#1a2130"
        ec = RED if present else BORDER
        rect = FancyBboxPatch((bx, by - box_h), box_w, box_h,
                              boxstyle="round,pad=0.008",
                              facecolor=fc, edgecolor=ec, lw=2.0, zorder=2)
        ax_right.add_patch(rect)
        symbol = "✓" if present else "–"
        sym_col = RED if present else TEXT_MUTED
        ax_right.text(bx + 0.05, by - box_h / 2, symbol,
                      fontsize=14, color=sym_col, va="center", fontweight="bold")
        ax_right.text(bx + 0.14, by - box_h / 2, name,
                      fontsize=10, color=TEXT_MAIN if present else TEXT_MUTED,
                      va="center", fontweight="bold" if present else "normal")

    plt.savefig(save_path, dpi=120, facecolor=BG, bbox_inches="tight")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
#  FRAMES 2–4 – SLIDING WINDOW HOPS
# ═══════════════════════════════════════════════════════════════════════════════

def make_window_frame(hop_idx, center, show_prediction, save_path):
    """
    hop_idx   : 0-based index (0, 1, 2)
    center    : center hour of the 2h window
    show_prediction: bool — show model prediction arrow at this hop
    """
    w_lo = center - WINDOW_SIZE / 2
    w_hi = center + WINDOW_SIZE / 2

    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    gs = GridSpec(4, 1, figure=fig,
                  left=0.08, right=0.95, top=0.90, bottom=0.08,
                  hspace=0.55)

    ax_map  = fig.add_subplot(gs[0])
    ax_med  = fig.add_subplot(gs[1])
    ax_pred = fig.add_subplot(gs[2])
    ax_gt   = fig.add_subplot(gs[3])

    set_dark_bg(fig, [ax_map, ax_med, ax_pred, ax_gt])

    # ── shared x formatting ──
    for ax in (ax_map, ax_med, ax_pred, ax_gt):
        ax.set_xlim(0, N_HOURS)
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(axis='x', colors=TEXT_MUTED, labelsize=9)
        ax.tick_params(axis='y', colors=TEXT_MUTED, labelsize=9)
        for sp in ax.spines.values(): sp.set_edgecolor(BORDER)

    for ax in (ax_map, ax_med, ax_pred):
        ax.set_xticks([])

    ax_gt.set_xlabel("Hours from ICU Admission", color=TEXT_MUTED, fontsize=10)
    ax_gt.set_xticks(range(0, N_HOURS + 1, 2))

    # Shade entire history (already observed) 
    for ax in (ax_map, ax_med, ax_pred, ax_gt):
        ax.axvspan(0, w_hi, color="#1c2535", alpha=0.4, zorder=0)

    # ── TITLE ──
    fig.text(0.5, 0.96,
             f"Sliding Context Window — Hop {hop_idx + 1}/3   "
             f"(Window: {w_lo:.1f}h – {w_hi:.1f}h)",
             ha="center", va="top", fontsize=16, fontweight="bold", color=TEXT_MAIN)
    fig.text(0.5, 0.92,
             f"ICU Stay: {PATIENT['id']}  |  2h Context Window  →  Model Output",
             ha="center", va="top", fontsize=10, color=TEXT_MUTED)

    # ══ PANEL 1: MAP ══════════════════════════════════════════════════════════
    ax_map.plot(TIME, MAP_VALUES, color="#607d8b", lw=1.0, alpha=0.5)  # faded full history
    # Bold only inside window
    win_mask = (TIME >= w_lo) & (TIME <= w_hi)
    ax_map.plot(TIME[win_mask], MAP_VALUES[win_mask], color=TEXT_MAIN, lw=2.2)
    ax_map.axhline(65, color=RED, lw=1.5, ls="--", alpha=0.7, label="65 mmHg threshold")
    draw_window_highlight(ax_map, center, WINDOW_SIZE, 35, 125)
    ax_map.set_ylim(35, 125)
    ax_map.set_ylabel("MAP\n(mmHg)", color=TEXT_MUTED, fontsize=9)
    ax_map.set_title("Mean Arterial Pressure", loc="left", fontsize=11,
                     color=TEXT_MAIN, fontweight="bold", pad=4)
    ax_map.legend(loc="upper right", fontsize=8,
                  facecolor=PANEL_BG, edgecolor=BORDER, labelcolor=TEXT_MUTED)

    # ══ PANEL 2: MEDICATIONS (stacked 0/1 bars per category) ═════════════════
    med_y_positions = {"Kristalloide": 3, "Elektrolyte": 2, "Antibiotika": 1}
    y_labels = {3: "Kristalloide", 2: "Elektrolyte", 1: "Antibiotika"}

    for name, vals in MEDS.items():
        ypos = med_y_positions[name]
        col  = CAT_COLORS[name]
        for t_idx, (t, v) in enumerate(zip(MED_TIME, vals)):
            if v == 1:
                in_win = w_lo <= t <= w_hi
                a = 0.85 if in_win else 0.25
                ax_med.bar(t, 0.6, width=0.45, bottom=ypos - 0.3,
                           color=col, alpha=a, zorder=3)

    draw_window_highlight(ax_med, center, WINDOW_SIZE, 0, 4.5, label=False)
    ax_med.axvline(w_lo, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    ax_med.axvline(w_hi, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    ax_med.set_ylim(0.2, 4.5)
    ax_med.set_yticks([1, 2, 3])
    ax_med.set_yticklabels(["Antibiotika", "Elektrolyte", "Kristalloide"],
                            fontsize=8, color=TEXT_MUTED)
    ax_med.set_title("Medikamentengabe (0/1 je 30-min-Intervall)", loc="left",
                     fontsize=11, color=TEXT_MAIN, fontweight="bold", pad=4)

    # Legend patches
    handles = [mpatches.Patch(facecolor=CAT_COLORS[n], label=n,
                              edgecolor="none") for n in CAT_COLORS]
    ax_med.legend(handles=handles, loc="upper right", fontsize=8,
                  facecolor=PANEL_BG, edgecolor=BORDER, labelcolor=TEXT_MUTED, ncol=3)

    # ══ PANEL 3: MODEL PREDICTIONS ═══════════════════════════════════════════
    ax_pred.set_ylim(0, 2)
    ax_pred.set_yticks([])
    ax_pred.set_title("Modellvorhersage (Katecholamin-Initiierung)", loc="left",
                      fontsize=11, color=TEXT_MAIN, fontweight="bold", pad=4)

    if show_prediction:
        for p in PREDICTIONS:
            if p["context_end"] <= w_hi:
                # arrow from context_end to target window
                draw_target_arrow(ax_pred, p["context_end"],
                                  p["target_start"], p["target_end"],
                                  y=1.0, color=ORANGE, alpha=0.85)
                ax_pred.plot(p["context_end"], 1.0, "o",
                             color=ORANGE, ms=7,
                             markeredgecolor=BG, markeredgewidth=1.5, zorder=9)

        ax_pred.text(GT_START + 0.1, 1.65, "Vorhergesagtes\nRisikoFenster",
                     fontsize=8, color=ORANGE, va="top")

    draw_window_highlight(ax_pred, center, WINDOW_SIZE, 0, 2, label=False)
    ax_pred.axvline(w_lo, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    ax_pred.axvline(w_hi, color=ACCENT, lw=1.2, ls="--", alpha=0.7)

    # ══ PANEL 4: GROUND TRUTH ════════════════════════════════════════════════
    ax_gt.set_ylim(0, 2)
    ax_gt.set_yticks([])
    ax_gt.set_title("Ground Truth: Katecholamin-Initiierungsfenster", loc="left",
                    fontsize=11, color=TEXT_MAIN, fontweight="bold", pad=4)

    # Show GT only if window has passed far enough
    gt_visible = w_hi >= GT_START - 1
    if gt_visible:
        rect = Rectangle((GT_START, 0.3), GT_END - GT_START, 1.4,
                         facecolor=RED, edgecolor=RED, alpha=0.4, lw=2, zorder=3)
        ax_gt.add_patch(rect)
        ax_gt.text((GT_START + GT_END) / 2, 1.65, "Vasopressor Start",
                   ha="center", fontsize=8, color=RED, fontweight="bold")
    else:
        ax_gt.text(N_HOURS / 2, 1.0,
                   "— noch nicht eingetreten —",
                   ha="center", va="center", fontsize=9,
                   color=TEXT_MUTED, style="italic")

    draw_window_highlight(ax_gt, center, WINDOW_SIZE, 0, 2, label=False)
    ax_gt.axvline(w_lo, color=ACCENT, lw=1.2, ls="--", alpha=0.7)
    ax_gt.axvline(w_hi, color=ACCENT, lw=1.2, ls="--", alpha=0.7)

    # ── current time marker ──
    for ax in (ax_map, ax_med, ax_pred, ax_gt):
        ax.axvline(w_hi, color=GREEN, lw=2.0, alpha=0.9, zorder=10)

    # Current time label
    ax_map.text(w_hi + 0.2, 118, f"t = {w_hi:.1f}h",
                fontsize=8, color=GREEN, va="top", fontweight="bold")

    # ── hop indicators at top ──
    for h_i, hc in enumerate(HOP_CENTERS):
        col = ACCENT if h_i == hop_idx else TEXT_MUTED
        lw  = 2.5    if h_i == hop_idx else 1.0
        for ax in (ax_map, ax_med, ax_pred, ax_gt):
            ax.axvspan(hc - WINDOW_SIZE/2, hc + WINDOW_SIZE/2,
                       color=col, alpha=0.04 if h_i != hop_idx else 0.0)

    plt.savefig(save_path, dpi=120, facecolor=BG, bbox_inches="tight")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSITION FRAME (brief animation between hops)
# ═══════════════════════════════════════════════════════════════════════════════

def make_transition_label_frame(from_center, to_center, save_path):
    """Quick overlay showing the hop arrow."""
    fig, ax = plt.subplots(figsize=(16, 9), facecolor=BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    fig.patch.set_facecolor(BG)

    ax.text(0.5, 0.58,
            f"⟶  Fenster rückt vor:  {from_center - WINDOW_SIZE/2:.0f}h – {from_center + WINDOW_SIZE/2:.0f}h"
            f"  →  {to_center - WINDOW_SIZE/2:.0f}h – {to_center + WINDOW_SIZE/2:.0f}h",
            ha="center", va="center", fontsize=20, color=ACCENT,
            fontweight="bold")
    ax.text(0.5, 0.44,
            "Sliding Context Window",
            ha="center", va="center", fontsize=13, color=TEXT_MUTED)

    plt.savefig(save_path, dpi=120, facecolor=BG, bbox_inches="tight")
    plt.close()

# ═══════════════════════════════════════════════════════════════════════════════
#  ASSEMBLE VIDEO
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_video(frame_paths, output_path, fps=4):
    """
    Assemble PNG frames into MP4. Tries (in order):
      1. OpenCV (cv2)          – usually available in conda ML envs
      2. imageio[ffmpeg]       – needs: pip install imageio[ffmpeg]
      3. subprocess ffmpeg     – uses system ffmpeg if on PATH
    Raises RuntimeError if none succeed.
    """
    import numpy as np
    from PIL import Image as PILImage

    # ── load & normalise all frames ────────────────────────────────────────
    frames_data = []
    for fp in frame_paths:
        img = PILImage.open(fp).convert("RGB")
        frames_data.append(np.array(img))

    h0, w0 = frames_data[0].shape[:2]
    w0 = w0 if w0 % 2 == 0 else w0 - 1   # libx264 requires even dimensions
    h0 = h0 if h0 % 2 == 0 else h0 - 1
    frames_data = [
        np.array(PILImage.fromarray(f).resize((w0, h0), PILImage.LANCZOS))
        for f in frames_data
    ]

    # ── attempt 1: OpenCV ──────────────────────────────────────────────────
    try:
        import cv2
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vw = cv2.VideoWriter(output_path, fourcc, fps, (w0, h0))
        if not vw.isOpened():
            raise RuntimeError("VideoWriter failed to open")
        for frame in frames_data:
            vw.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        vw.release()
        print(f"✅  Video saved (cv2): {output_path}")
        return
    except ImportError:
        print("cv2 not available, trying imageio …")
    except Exception as e:
        print(f"cv2 failed ({e}), trying imageio …")

    # ── attempt 2: imageio ffmpeg ──────────────────────────────────────────
    try:
        import imageio.v2 as iio2
        writer = iio2.get_writer(output_path, fps=fps,
                                 format="ffmpeg", codec="libx264",
                                 quality=8, macro_block_size=1)
        for frame in frames_data:
            writer.append_data(frame)
        writer.close()
        print(f"✅  Video saved (imageio): {output_path}")
        return
    except Exception as e:
        print(f"imageio failed ({e}), trying subprocess ffmpeg …")

    # ── attempt 3: subprocess ffmpeg ──────────────────────────────────────
    try:
        import subprocess, os, tempfile as _tf
        tmp_dir = _tf.mkdtemp()
        for i, frame in enumerate(frames_data):
            PILImage.fromarray(frame).save(f"{tmp_dir}/frame_{i:05d}.png")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", f"{tmp_dir}/frame_%05d.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        # cleanup tmp pngs
        for f in Path(tmp_dir).iterdir(): f.unlink()
        Path(tmp_dir).rmdir()
        if result.returncode == 0:
            print(f"✅  Video saved (ffmpeg CLI): {output_path}")
            return
        else:
            raise RuntimeError(result.stderr[-500:])
    except FileNotFoundError:
        raise RuntimeError(
            "No video backend found!\n"
            "Install one of:\n"
            "  conda install -c conda-forge opencv\n"
            "  pip install imageio[ffmpeg]\n"
            "  conda install -c conda-forge ffmpeg"
        )

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    tmp = Path(tempfile.mkdtemp())
    frames = []

    print("Rendering metadata frame …")
    p = tmp / "f000_meta.png"
    make_metadata_frame(p)
    # Hold the metadata frame for ~3 s at 4 fps = 12 duplicates
    frames += [str(p)] * 14

    for hop_i, center in enumerate(HOP_CENTERS):
        print(f"Rendering hop {hop_i+1} frame …")

        # transition
        if hop_i > 0:
            tp = tmp / f"f{hop_i:02d}_trans.png"
            make_transition_label_frame(HOP_CENTERS[hop_i - 1], center, tp)
            frames += [str(tp)] * 6  # ~1.5 s

        show_pred = (center >= 18.0)  # predictions only appear near the event
        p = tmp / f"f{hop_i:02d}_hop.png"
        make_window_frame(hop_i, center, show_pred, p)
        frames += [str(p)] * 16   # ~4 s per hop frame

    # Final hold on last frame
    frames += [frames[-1]] * 8

    out_path = "YOUR-PATH/actionable-hypotension/simulation/sliding_window_methodology.mp4"
    print("Assembling MP4 …")
    assemble_video(frames, out_path, fps=4)

    # cleanup
    for f in tmp.iterdir(): f.unlink()
    tmp.rmdir()

if __name__ == "__main__":
    main()
