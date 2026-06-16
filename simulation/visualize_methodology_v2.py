"""
Sliding-Window-Methodik – Visualisierung als MP4
=================================================
Stil:  Heller Hintergrund analog zur Originalsimulation
Inhalt: 3 Hops des 2h-Kontextfensters (Box springt über den Zeitstrahl)
        MAP-Kurve, Medikamente (0/1 pro 2h-Fenster), Modellvorhersage, Ground Truth
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.gridspec import GridSpec
import tempfile
import subprocess
from pathlib import Path
from PIL import Image as PILImage

# ─── Style (hell, wie die Original-Simulation) ────────────────────────────────
plt.rcParams.update({
    'font.family':        'DejaVu Sans',
    'axes.spines.top':    False,
    'axes.spines.right':  False,
    'axes.facecolor':     'white',
    'figure.facecolor':   'white',
    'axes.edgecolor':     '#aaaaaa',
    'axes.grid':          True,
    'grid.color':         '#e0e0e0',
    'grid.linewidth':     0.5,
    'xtick.color':        '#444444',
    'ytick.color':        '#444444',
})

# ─── Farben ────────────────────────────────────────────────────────────────────
C_MAP_LINE   = '#1a1a2e'
C_MAP_THRESH = '#e63946'
C_WIN_FILL   = '#dbeafe'      # helles Blau – Kontextfenster
C_WIN_EDGE   = '#2563eb'
C_TIME_LINE  = '#2563eb'      # aktuelle Zeit (senkrechte Linie)
C_GT_PAST    = '#b91c1c'      # Ground-Truth vergangen
C_GT_NOW     = '#ef4444'      # Ground-Truth aktiv
C_PRED_FILL  = '#f97316'
C_TREAT      = '#16a34a'
C_META_BG    = '#f8f9fa'
C_META_EDGE  = '#dee2e6'

MED_FARBEN = {
    "Kristalloide": "#2196f3",
    "Elektrolyte":  "#9c27b0",
    "Antibiotika":  "#4caf50",
}

# ─── Fake-Daten ───────────────────────────────────────────────────────────────
np.random.seed(42)
N_H   = 24                            # Aufenthaltsdauer in Stunden
ZEIT  = np.linspace(0, N_H, 300)

def make_map(t):
    base  = 76 + 9 * np.sin(t * 0.28) - 4 * np.sin(t * 1.05)
    dip1  = -28 * np.exp(-0.5 * ((t - 9)  / 0.9) ** 2)
    dip2  = -20 * np.exp(-0.5 * ((t - 19) / 1.1) ** 2)
    noise = np.random.normal(0, 2.5, len(t))
    return np.clip(base + dip1 + dip2 + noise, 32, 132)

MAP_WERTE = make_map(ZEIT)

# Medikamenten-Entscheidung pro 2h-Fenster (0/1)
# Wir bilden die Fenstergrenzen, für jedes wird entschieden ob gegeben
rng_m = np.random.default_rng(99)

def meds_fuer_fenster(fenster_start, fenster_ende):
    """Gibt dict {Kategorie: bool} zurück – Entscheidung für dieses 2h-Fenster."""
    return {
        "Kristalloide": bool(rng_m.random() < 0.45),
        "Elektrolyte":  bool(rng_m.random() < 0.30),
        "Antibiotika":  bool(rng_m.random() < 0.18),
    }

# Alle 2h-Fenster vorberechnen für den gesamten Zeitstrahl
FENSTER_GROESSE = 2.0                    # Stunden
HOP_ZENTREN     = [5.0, 12.0, 19.0]     # 3 Hops

# Erzeuge Medikamentendaten für alle möglichen 2h-Fenster im Aufenthalt
ALLE_FENSTER_STARTS = np.arange(0, N_H, FENSTER_GROESSE)
rng_all = np.random.default_rng(7)
MED_TIMELINE = {}   # start_h -> {Kategorie: bool}
for fs in ALLE_FENSTER_STARTS:
    MED_TIMELINE[fs] = {
        "Kristalloide": bool(rng_all.random() < 0.45),
        "Elektrolyte":  bool(rng_all.random() < 0.30),
        "Antibiotika":  bool(rng_all.random() < 0.18),
    }

# Ground-Truth: Katecholamin-Initiierung Stunde 19–21
GT_START = 19.0
GT_ENDE  = 21.0

# Vorhersagen: bei Hop 3 (Fenster ~18–20) werden sie sichtbar
VORHERSAGEN = [
    {"kontext_start": 17.0, "kontext_ende": 19.0, "ziel_start": 19.5, "ziel_ende": 21.5},
    {"kontext_start": 17.5, "kontext_ende": 19.5, "ziel_start": 19.0, "ziel_ende": 21.0},
]

# Patient
PATIENT = {
    "id":           "",
    "geschlecht":   "Männlich",
    "alter":        67,
    "ethnie":       "Kaukasisch",
    "groesse_cm":   178,
    "gewicht_kg":   84,
    "vorerkrankungen": {
        "Art. Hypertonie":     True,
        "Diabetes mellitus":   True,
        "Herzinsuffizienz":    True,
        "Chron. Niereninsuff.": False,
        "KHK":                 True,
        "Sepsis (Voraufn.)":   False,
    },
}
BMI = PATIENT["gewicht_kg"] / (PATIENT["groesse_cm"] / 100) ** 2

# ─── Zielauflösung ────────────────────────────────────────────────────────────
TARGET_W, TARGET_H, DPI = 1920, 1080, 120

def _fig_speichern(fig, pfad):
    fig.set_size_inches(TARGET_W / DPI, TARGET_H / DPI)
    plt.savefig(pfad, dpi=DPI, facecolor='white', bbox_inches=None)
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════════
#  Metadata-Panel (oben, kompakt wie Original)
# ═══════════════════════════════════════════════════════════════════════════════

def meta_panel_zeichnen(ax):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')

    # Hintergrund
    ax.add_patch(Rectangle((0.005, 0.03), 0.99, 0.94,
                            facecolor=C_META_BG, edgecolor=C_META_EDGE,
                            linewidth=1.5, zorder=0))

    # ── Demographie (links) ──
    demo_text = (
        f"Geschlecht: {PATIENT['geschlecht']}  |  "
        f"Alter: {PATIENT['alter']} J.  |  "
        f"Ethnie: {PATIENT['ethnie']}  |  "
        f"Größe: {PATIENT['groesse_cm']} cm  |  "
        f"Gewicht: {PATIENT['gewicht_kg']} kg  |  "
        f"BMI: {BMI:.1f}"
    )
    ax.text(0.01, 0.80, demo_text, fontsize=9.5, va='top',
            color='#222222', family='monospace')

    # ── Vorerkrankungen (Boxen) ──
    ax.text(0.01, 0.55, 'Vorerkrankungen:', fontsize=10,
            fontweight='bold', va='top', color='#333333')

    items    = list(PATIENT["vorerkrankungen"].items())
    box_w    = 0.14
    box_h    = 0.28
    x_start  = 0.01
    x_gap    = 0.155
    y_box    = 0.42

    for idx, (name, vorhanden) in enumerate(items):
        bx = x_start + idx * x_gap
        fc = '#ffcccc' if vorhanden else '#e8f4f8'
        ec = '#cc0000' if vorhanden else '#b0bec5'
        tc = '#cc0000' if vorhanden else '#666666'
        sym = '✓' if vorhanden else '−'
        ax.add_patch(Rectangle((bx, y_box - box_h), box_w, box_h,
                                facecolor=fc, edgecolor=ec,
                                linewidth=1.8, zorder=1))
        ax.text(bx + 0.015, y_box - box_h / 2 + 0.02, sym,
                fontsize=11, color=tc, va='center', fontweight='bold')
        ax.text(bx + 0.042, y_box - box_h / 2, name,
                fontsize=8, color=tc, va='center',
                fontweight='bold' if vorhanden else 'normal')


# ═══════════════════════════════════════════════════════════════════════════════
#  Einzelner Frame: ein Hop
# ═══════════════════════════════════════════════════════════════════════════════

def frame_hop(hop_idx, w_start, w_ende, speicherpfad):
    """
    Zeichnet einen Frame mit:
      - Metadaten-Panel oben
      - 4 Panels: MAP | Medikamente | Vorhersage | Ground Truth
    Das Kontextfenster [w_start, w_ende] wird als blauer Block hervorgehoben.
    """
    fig = plt.figure(figsize=(TARGET_W / DPI, TARGET_H / DPI),
                     facecolor='white', constrained_layout=False)

    gs = fig.add_gridspec(
        5, 1,
        left=0.07, right=0.97, top=0.93, bottom=0.07,
        height_ratios=[0.85, 1, 1, 0.8, 0.8],
        hspace=0.55,
    )

    ax_meta = fig.add_subplot(gs[0])
    ax_map  = fig.add_subplot(gs[1])
    ax_med  = fig.add_subplot(gs[2])
    ax_pred = fig.add_subplot(gs[3])
    ax_gt   = fig.add_subplot(gs[4])

    # Titel
    fig.suptitle(
        f"ICU-Aufenthalt {PATIENT['id']}  –  "
        f"Schritt {hop_idx + 1}/3:  Kontextfenster {w_start:.0f}h – {w_ende:.0f}h",
        fontsize=14, fontweight='bold', y=0.975, color='#111111',
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    meta_panel_zeichnen(ax_meta)

    # ── Gemeinsame X-Achse ────────────────────────────────────────────────────
    for ax in (ax_map, ax_med, ax_pred, ax_gt):
        ax.set_xlim(0, N_H)
        ax.set_facecolor('white')
        for sp in ax.spines.values():
            sp.set_edgecolor('#aaaaaa')
        ax.grid(True, color='#e0e0e0', linewidth=0.5, zorder=0)
        # Kontextfenster-Box (helles Blau)
        ax.axvspan(w_start, w_ende, color=C_WIN_FILL, alpha=0.55, zorder=1)
        ax.axvline(w_start, color=C_WIN_EDGE, lw=1.5, ls='--', alpha=0.8, zorder=3)
        ax.axvline(w_ende,  color=C_WIN_EDGE, lw=1.5, ls='--', alpha=0.8, zorder=3)
        # Aktuelle Zeit (Ende des Fensters) als durchgezogene blaue Linie
        ax.axvline(w_ende, color=C_TIME_LINE, lw=2.5, alpha=0.9, zorder=4)

    for ax in (ax_map, ax_med, ax_pred):
        ax.set_xticks([])

    ax_gt.set_xlabel('Stunden seit ICU-Aufnahme', fontsize=11, fontweight='bold',
                     color='#333333')
    ax_gt.set_xticks(range(0, N_H + 1, 2))
    ax_gt.tick_params(axis='x', colors='#444444', labelsize=9)

    # ── Panel 1: MAP ──────────────────────────────────────────────────────────
    ax_map.plot(ZEIT, MAP_WERTE, color='#444444', lw=1.0, alpha=0.35, zorder=2)
    # Fett im Fenster
    m = (ZEIT >= w_start) & (ZEIT <= w_ende)
    ax_map.plot(ZEIT[m], MAP_WERTE[m], color=C_MAP_LINE, lw=2.2,
                marker='o', markersize=3, zorder=5)
    ax_map.axhline(65, color=C_MAP_THRESH, ls='--', lw=1.8, alpha=0.7,
                   label='Hypotonie-Schwelle (65 mmHg)', zorder=3)
    ax_map.set_ylim(35, 125)
    ax_map.set_ylabel('MAP (mmHg)', fontsize=10, fontweight='bold', color='#333333')
    ax_map.set_title('Mittlerer Arterieller Druck (MAP)', loc='left',
                     fontsize=11, fontweight='bold', color='#111111', pad=3)
    ax_map.legend(loc='upper right', fontsize=9, framealpha=0.9)

    # Fenster-Label
    ax_map.annotate(
        '', xy=(w_ende, 118), xytext=(w_start, 118),
        arrowprops=dict(arrowstyle='<->', color=C_WIN_EDGE, lw=1.6),
        zorder=6,
    )
    ax_map.text((w_start + w_ende) / 2, 122, '2h Kontext',
                ha='center', fontsize=8, color=C_WIN_EDGE,
                fontweight='bold', zorder=6)

    # ── Panel 2: Medikamente (pro 2h-Fenster) ─────────────────────────────────
    ax_med.set_ylim(0, 4.2)
    ax_med.set_yticks([1, 2, 3])
    ax_med.set_yticklabels(['Antibiotika', 'Elektrolyte', 'Kristalloide'],
                            fontsize=9, color='#333333')
    ax_med.set_title('Medikamentengabe (pro 2h-Kontextfenster)',
                     loc='left', fontsize=11, fontweight='bold',
                     color='#111111', pad=3)

    y_pos = {'Kristalloide': 3, 'Elektrolyte': 2, 'Antibiotika': 1}

    for fs, med_dict in MED_TIMELINE.items():
        fe = fs + FENSTER_GROESSE
        if fe > N_H:
            continue
        ist_aktuell = (fs == w_start)   # genau das aktive Fenster
        for kat, gegeben in med_dict.items():
            if not gegeben:
                continue
            col   = MED_FARBEN[kat]
            alpha = 0.90 if ist_aktuell else 0.28
            lw_ec = 1.8  if ist_aktuell else 0.0
            ax_med.add_patch(Rectangle(
                (fs + 0.05, y_pos[kat] - 0.35), FENSTER_GROESSE - 0.1, 0.7,
                facecolor=col, edgecolor=col if ist_aktuell else 'none',
                linewidth=lw_ec, alpha=alpha, zorder=3 if ist_aktuell else 2,
            ))

    handles = [mpatches.Patch(facecolor=MED_FARBEN[n], label=n, alpha=0.85)
               for n in MED_FARBEN]
    ax_med.legend(handles=handles, loc='upper right', fontsize=9,
                  framealpha=0.9, ncol=3)

    # ── Panel 3: Modellvorhersage ──────────────────────────────────────────────
    ax_pred.set_ylim(0, 2)
    ax_pred.set_yticks([])
    ax_pred.set_title('Modellvorhersage: Katecholamin-Initiierung',
                      loc='left', fontsize=11, fontweight='bold',
                      color='#111111', pad=3)

    zeige_pred = (w_ende >= GT_START - 1.5)
    if zeige_pred:
        for v in VORHERSAGEN:
            if v['kontext_ende'] <= w_ende:
                # Zielfenster
                ax_pred.add_patch(Rectangle(
                    (v['ziel_start'], 0.3),
                    v['ziel_ende'] - v['ziel_start'], 1.4,
                    facecolor=C_PRED_FILL, edgecolor='#c2410c',
                    alpha=0.55, linewidth=1.5, zorder=3,
                ))
                # Pfeil Kontext → Ziel
                ax_pred.annotate(
                    '', xy=(v['ziel_start'], 1.0),
                    xytext=(v['kontext_ende'], 1.0),
                    arrowprops=dict(arrowstyle='-|>', color='#c2410c',
                                   lw=1.8, connectionstyle='arc3,rad=-0.3'),
                    zorder=5,
                )
                ax_pred.plot(v['kontext_ende'], 1.0, 'o',
                             color=C_PRED_FILL, ms=7,
                             markeredgecolor='#c2410c', markeredgewidth=1.4,
                             zorder=6)
        ax_pred.text(GT_START + 0.1, 1.72, 'Vorhergesagtes\nRisikoFenster',
                     fontsize=8, color='#c2410c', va='top', fontweight='bold')
    else:
        ax_pred.text(N_H / 2, 1.0,
                     '— Kein Ereignis im aktuellen Horizont —',
                     ha='center', va='center', fontsize=9,
                     color='#888888', style='italic')

    # ── Panel 4: Ground Truth ─────────────────────────────────────────────────
    ax_gt.set_ylim(0, 2)
    ax_gt.set_yticks([])
    ax_gt.set_title('Ground Truth: Katecholamin-Initiierungsfenster',
                    loc='left', fontsize=11, fontweight='bold',
                    color='#111111', pad=3)

    if w_ende >= GT_START - 0.5:
        col_gt = C_GT_PAST if w_ende >= GT_ENDE else C_GT_NOW
        ax_gt.add_patch(Rectangle(
            (GT_START, 0.3), GT_ENDE - GT_START, 1.4,
            facecolor=col_gt, edgecolor='#7f1d1d',
            alpha=0.50, linewidth=1.8, zorder=3,
        ))
        ax_gt.text((GT_START + GT_ENDE) / 2, 1.72,
                   'Vasopressor-Gabe',
                   ha='center', fontsize=9, color='#7f1d1d', fontweight='bold')
        ax_gt.text(GT_START, 0.05, '▼', ha='center', fontsize=14,
                   color='#7f1d1d', fontweight='bold')
    else:
        ax_gt.text(N_H / 2, 1.0,
                   '— Noch nicht eingetreten —',
                   ha='center', va='center', fontsize=9,
                   color='#888888', style='italic')

    # t-Label an aktueller Zeit
    ax_map.text(w_ende + 0.25, 117, f't = {w_ende:.0f}h',
                fontsize=9, color=C_TIME_LINE, va='top', fontweight='bold')

    _fig_speichern(fig, speicherpfad)


# ═══════════════════════════════════════════════════════════════════════════════
#  Video: Frames zusammensetzen via ffmpeg
# ═══════════════════════════════════════════════════════════════════════════════

def video_erstellen(frame_pfade, ausgabe_pfad, fps=4):
    tmp = Path(tempfile.mkdtemp())
    for i, src in enumerate(frame_pfade):
        img = PILImage.open(src).convert('RGB').resize(
            (TARGET_W, TARGET_H), PILImage.LANCZOS)
        img.save(tmp / f'frame_{i:05d}.png')

    cmd = [
        'ffmpeg', '-y',
        '-framerate', str(fps),
        '-i',         str(tmp / 'frame_%05d.png'),
        '-c:v',       'libx264',
        '-preset',    'slow',
        '-crf',       '18',
        '-pix_fmt',   'yuv420p',
        '-movflags',  '+faststart',
        ausgabe_pfad,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)

    for f in tmp.iterdir(): f.unlink()
    tmp.rmdir()

    if res.returncode != 0:
        raise RuntimeError(f'ffmpeg Fehler:\n{res.stderr[-600:]}')
    print(f'✅  Video gespeichert: {ausgabe_pfad}')


# ═══════════════════════════════════════════════════════════════════════════════
#  Hauptprogramm
# ═══════════════════════════════════════════════════════════════════════════════

def main(ausgabe_pfad='sliding_window_methodik.mp4', fps=4):
    tmp  = Path(tempfile.mkdtemp())
    frames = []

    for hop_i, zentrum in enumerate(HOP_ZENTREN):
        w_lo = zentrum - FENSTER_GROESSE / 2
        w_hi = zentrum + FENSTER_GROESSE / 2
        print(f'Rendere Hop {hop_i + 1}/3  (Fenster {w_lo:.0f}h – {w_hi:.0f}h) …')

        hp = tmp / f'hop_{hop_i:02d}.png'
        frame_hop(hop_i, w_lo, w_hi, hp)
        frames += [str(hp)] * (fps * 5)   # 5 Sekunden pro Hop

    # Letzten Frame 2 s halten
    frames += [frames[-1]] * (fps * 2)

    print(f'Erzeuge MP4 aus {len(frames)} Frames …')
    video_erstellen(frames, ausgabe_pfad, fps=fps)

    for f in tmp.iterdir(): f.unlink()
    tmp.rmdir()


if __name__ == '__main__':
    main()