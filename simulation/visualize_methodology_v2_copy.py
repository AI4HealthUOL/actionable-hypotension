"""
ICU Sampling & Target Visualization – Präsentations-Layout
===========================================================
Layout: 3 horizontale Balken (Reihen) + Target-Box rechts neben MAP
  ROW 1: Patientenmetadaten  (volle Breite)
  ROW 2: MAP-Dynamik + Feature-Box (wandert mit Fenster) | TARGET-Box (rechts, schmal)
  ROW 3: Medikamentengabe    (volle Breite)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Rectangle, FancyBboxPatch
from pathlib import Path
import tempfile, subprocess, shutil
from PIL import Image as PILImage

# ── Farben ────────────────────────────────────────────────────────────────────
C_WIN_FILL   = '#dbeafe'
C_LOOK_FILL  = '#fef3c7'
C_LOOK_EDGE  = '#f59e0b'
C_TARGET_POS = '#dc2626'
C_TARGET_NEG = '#16a34a'
C_MAP_DIM    = '#cbd5e1'
C_MAP_BOLD   = '#1e293b'
C_MAP_THRESH = '#ef4444'
C_FEAT_BG    = '#f0f9ff'
C_FEAT_EDGE  = '#2563eb'

C_ROW1_BG = '#1e3a5f'   # dunkles Blau  – Metadaten-Header
C_ROW3_BG = '#14532d'   # dunkles Grün  – Medikamenten-Header
C_ROW2_BG = '#1e293b'   # fast schwarz  – MAP-Header

MED_FARBEN = {"Kristalloide": "#3b82f6",
              "Elektrolyte":  "#a855f7",
              "Antibiotika":  "#22c55e"}

TARGET_W, TARGET_H, DPI = 1920, 1080, 120

# ── Fake Daten ────────────────────────────────────────────────────────────────
N_H  = 24
ZEIT = np.linspace(0, N_H, 600)

def make_map(t):
    base  = 78 + 8 * np.sin(t * 0.3)
    dip1  = -25 * np.exp(-0.5 * ((t - 9)  / 0.9) ** 2)
    dip2  = -20 * np.exp(-0.5 * ((t - 19) / 1.0) ** 2)
    noise = np.random.RandomState(42).normal(0, 2, len(t))
    return np.clip(base + dip1 + dip2 + noise, 35, 130)

MAP_WERTE = make_map(ZEIT)

VASO_STARTS      = [9.25, 19.25]
FENSTER_GROESSE  = 2.0
LOOKAHEAD        = 0.25   # 15 min

PATIENT = {
    "geschlecht": "Männlich", "alter": 67, "ethnie": "Kaukasisch",
    "groesse_cm": 178, "gewicht_kg": 84,
    "vorerkrankungen": {"Art. Hypertonie": True, "Diabetes mellitus": True,
                        "Herzinsuffizienz": True, "Chron. \nNiereninsuff.": False}
}
BMI = PATIENT["gewicht_kg"] / (PATIENT["groesse_cm"] / 100) ** 2

rng      = np.random.default_rng(7)
ALLE_FS  = np.arange(0, N_H, FENSTER_GROESSE)
MED_TIMELINE = {
    float(fs): {
        "Kristalloide": rng.random() < 0.35,
        "Elektrolyte":  rng.random() < 0.30,
        "Antibiotika":  rng.random() < 0.05
    } for fs in ALLE_FS
}

def target_label(w_end):
    return int(any(w_end <= t <= w_end + LOOKAHEAD for t in VASO_STARTS))


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

# ── Grid-Header-Zeichenfunktion ───────────────────────────────────────────────
def draw_row_header(ax, title, bg_color):
    """Zeichnet Header mittig in der Zeile ohne Überlappung."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=bg_color, transform=ax.transAxes, clip_on=False))
    ax.text(0.5, 0.5, title, color='white', fontsize=13,
            fontweight='bold', ha='center', va='center', transform=ax.transAxes)



# ── Patientenmetadaten-Content ───────────────────────────────────────────────
def draw_meta_content(ax):
    """Patientenmetadaten – sauber vertikal zentriert."""
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor='#f8fafc', edgecolor='#e2e8f0', linewidth=1))

    # Demografische Daten mittig vertikal
    demo = (f"  {PATIENT['geschlecht']}  ·  {PATIENT['alter']} Jahre  ·  "
            f"{PATIENT['ethnie']}  ·  BMI {BMI:.1f}")
    ax.text(0.01, 0.7, demo, fontsize=12, va='center', fontweight='bold', color='#1e293b')

    # Vorerkrankungen als Chips nebeneinander
    x = 0.01
    y = 0.3
    for k, v in PATIENT["vorerkrankungen"].items():
        label = f"  {'✓' if v else '✗'}  {k}  "
        bg    = '#dcfce7' if v else '#fee2e2'
        fc    = '#166534' if v else '#991b1b'
        ax.text(x, y, label, fontsize=10.5, va='center',
                color=fc, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=bg, edgecolor=fc, linewidth=1))
        x += len(label) * 0.012 + 0.02


def draw_map_panel(ax, w_start, w_end):
    """MAP-Kurve mit Kontextfenster & Look-Ahead."""
    ax.set_facecolor('#f8fafc')
    ax.plot(ZEIT, MAP_WERTE, color=C_MAP_DIM, lw=1.2, zorder=1)

    # Kontextfenster
    ax.axvspan(w_start, w_end,
               color=C_WIN_FILL, alpha=0.75, zorder=2, label='2h Kontextfenster')

    # Look-Ahead
    ax.axvspan(w_end, w_end + LOOKAHEAD,
               color=C_LOOK_FILL, alpha=0.9, zorder=2,
               label='15min Target Fenster')
    for side in [w_end, w_end + LOOKAHEAD]:
        ax.axvline(side, color=C_LOOK_EDGE, lw=1.5, ls='--', zorder=3)

    # aktiver Abschnitt fett
    m = (ZEIT >= w_start) & (ZEIT <= w_end)
    ax.plot(ZEIT[m], MAP_WERTE[m], color=C_MAP_BOLD, lw=2.8, zorder=4)

    # Schwellenwert
    ax.axhline(65, color=C_MAP_THRESH, ls='--', lw=1.5,
               label='MAD < 65 mmHg', zorder=3)

    # Vasopressor-Zeitpunkte
    for i, t in enumerate(VASO_STARTS):
        ax.axvline(t, color=C_TARGET_POS, lw=2.2, zorder=5,
                   label='Kat-Therapie-Start' if i == 0 else '')

    ax.set_ylabel('MAD (mmHg)', fontsize=10, fontweight='bold')
    #ax.set_xlabel('Zeit (h)', fontsize=9)
    ax.tick_params(axis='x', which='both', bottom=False, labelbottom=False)
    ax.spines['bottom'].set_visible(False)
    ax.set_xlim(0, N_H)
    ax.set_ylim(30, 135)
    ax.tick_params(labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    leg = ax.legend(loc='upper right', fontsize=7.5, framealpha=0.85,
                    ncol=2, handlelength=1.4)


def draw_feature_box(ax, w_start, w_end):
    """Feature-Extraktion – Box wandert mit dem Kontextfenster."""
    m   = (ZEIT >= w_start) & (ZEIT <= w_end)
    win = MAP_WERTE[m]

    if len(win) > 1:
        mean_v = np.mean(win)
        min_v  = np.min(win)
        max_v  = np.max(win)
        std_v  = np.std(win)
        slope  = np.polyfit(ZEIT[m], win, 1)[0]
    else:
        mean_v = min_v = max_v = std_v = slope = float('nan')

    lines = [
        ("Ø MAD",   f"{mean_v:.1f} mmHg"),
        ("Min",     f"{min_v:.1f} mmHg"),
        ("Max",     f"{max_v:.1f} mmHg"),
        ("Std",     f"{std_v:.1f}"),
        ("Trend",   f"{slope:+.2f} /h"),
    ]

    ax.axis('off')
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.03, 0.04), 0.94, 0.92,
                                boxstyle="round,pad=0.02",
                                facecolor=C_FEAT_BG,
                                edgecolor=C_FEAT_EDGE, linewidth=2))
    ax.text(0.5, 0.93, "Statistische Merkmale", ha='center', va='top',
            fontsize=10, fontweight='bold', color='#1e40af')

    n = len(lines)
    for i, (lbl, val) in enumerate(lines):
        y = 0.82 - i * (0.75 / n)
        ax.text(0.08, y, lbl, fontsize=9, color='#475569', va='center')
        ax.text(0.95, y, val, fontsize=9.5, color='#1e293b',
                va='center', ha='right', fontweight='bold',
                fontfamily='monospace')


def draw_target_box(ax, w_end):
    """TARGET-Label rechts neben dem MAP-Panel."""
    y = target_label(w_end)
    ax.axis('off')
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    bg  = '#fee2e2' if y else '#dcfce7'
    fc  = C_TARGET_POS if y else C_TARGET_NEG
    txt = "JA" if y else "NEIN"

    ax.add_patch(FancyBboxPatch((0.05, 0.1), 0.90, 0.80,
                                boxstyle="round,pad=0.04",
                                facecolor=bg,
                                edgecolor=fc, linewidth=3))
    ax.text(0.5, 0.72, "TARGET", ha='center', va='center',
            fontsize=11, fontweight='bold', color=fc)
    ax.text(0.5, 0.42, "Katecholamintherapie Beginn \nin 15 min?", ha='center', va='center',
            fontsize=10, color='#64748b', linespacing=1.4)
    ax.text(0.5, 0.16, txt, ha='center', va='center',
            fontsize=22, fontweight='bold', color=fc)


# ── Medikamenten-Panel ───────────────────────────────────────────────────────
def draw_med_panel(ax, w_end):
    """Medikamentengabe-Panel sauber vertikal zentriert."""
    ax.set_facecolor('#f8fafc')
    ax.set_xlim(0, N_H)
    ax.set_ylim(0.5, 3.5)  # enger, damit Header nicht überlappt
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(['Antibiotika', 'Elektrolyte', 'Kristalloide'],
                       fontsize=9.5, fontweight='bold')
    ax.tick_params(axis='x', labelsize=8)
    ax.set_xlabel('Zeit (h)', fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Aktuelles Fenster markieren
    ax.axvspan(w_end - FENSTER_GROESSE, w_end,
               color=C_WIN_FILL, alpha=0.5, zorder=1)

    kat_list = list(MED_FARBEN.keys())
    for fs, med_dict in MED_TIMELINE.items():
        for idx, kat in enumerate(kat_list):
            if med_dict.get(kat, False):
                ax.add_patch(Rectangle((fs, idx + 0.65), FENSTER_GROESSE, 0.7,
                                       facecolor=MED_FARBEN[kat],
                                       alpha=0.85, zorder=2,
                                       edgecolor='white', linewidth=0.5))

    # Legende
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, alpha=0.85)
               for c in MED_FARBEN.values()]
    ax.legend(handles, MED_FARBEN.keys(),
              loc='upper right', fontsize=8, framealpha=0.9,
              ncol=3, handlelength=1.2)



# ── Frame erzeugen ────────────────────────────────────────────────────────────

def frame_hop(w_start, w_end, pfad):
    fig = plt.figure(figsize=(TARGET_W / DPI, TARGET_H / DPI),
                     facecolor='white')

    gs = gridspec.GridSpec(
        3, 2,
        figure=fig,
        width_ratios=[0.82, 0.18],   # ICU-Bereich konstant breit
        height_ratios=[0.18, 0.52, 0.30],
        hspace=0.06,
        wspace=0.10,
        left=0.08, right=0.97,
        top=0.96, bottom=0.05
    )
    

    # ─────────────────────────────────────────
    # ROW 1 – META (nur Content-Spalte)
    # ─────────────────────────────────────────
    ax_meta = fig.add_subplot(gs[0, 0])
    ax_meta_right = fig.add_subplot(gs[0, 1])
    ax_meta_right.axis("off")

    draw_meta_content(ax_meta)

    # ─────────────────────────────────────────
    # ROW 2 – MAP + TARGET
    # ─────────────────────────────────────────
    ax_map = fig.add_subplot(gs[1, 0])
    ax_tgt = fig.add_subplot(gs[1, 1])

    draw_map_panel(ax_map, w_start, w_end)
    draw_target_box(ax_tgt, w_end)

    # Feature-Box
    feat_x = (w_start / N_H) + 0.01
    feat_x = min(feat_x, 0.70)
    ax_feat = ax_map.inset_axes([feat_x, 0.55, 0.18, 0.40])
    draw_feature_box(ax_feat, w_start, w_end)

    # ─────────────────────────────────────────
    # ROW 3 – MED (nur Content-Spalte)
    # ─────────────────────────────────────────
    ax_med = fig.add_subplot(gs[2, 0], sharex=ax_map)
    ax_med_right = fig.add_subplot(gs[2, 1])
    ax_med_right.axis("off")

    draw_med_panel(ax_med, w_end)

    plt.savefig(pfad, dpi=DPI, bbox_inches=None,
                pad_inches=0.03, facecolor='white')
    plt.close(fig)

# ── Video erstellen ───────────────────────────────────────────────────────────

def video_erstellen(frames, ausgabe, fps=4):
    tmp = Path(tempfile.mkdtemp())
    try:
        for i, f in enumerate(frames):
            PILImage.open(f).resize((TARGET_W, TARGET_H)).save(
                tmp / f'frame_{i:05d}.png')
        cmd = ['ffmpeg', '-y', '-framerate', str(fps),
               '-i', str(tmp / 'frame_%05d.png'),
               '-c:v', 'libx264', '-pix_fmt', 'yuv420p', ausgabe]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── Main ─────────────────────────────────────────────────────────────────────

def main(ausgabe='sampling_overview.mp4'):
    SCHRITT = 0.25   # 15-min-Schritte
    starts  = np.arange(0, N_H - FENSTER_GROESSE + SCHRITT, SCHRITT)
    tmp     = Path(tempfile.mkdtemp())
    frames  = []
    try:
        for w_start in starts:
            w_end = w_start + FENSTER_GROESSE
            pfad  = tmp / f'frame_{int(round(w_start * 100)):05d}.png'
            frame_hop(w_start, w_end, pfad)
            frames.append(str(pfad))
        frames += [frames[-1]] * 8   # letzten Frame halten
        video_erstellen(frames, ausgabe, fps=4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'✅  Video gespeichert: {ausgabe}')


if __name__ == "__main__":
    main()