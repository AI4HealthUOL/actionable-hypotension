import cv2
import numpy as np

from pathlib import Path

# Use this if your inputs are PNGs.
# If you have PDFs, see conversion note below.

base_dir = Path(__file__).parent

# List images for each row
row_files = [
    ["mix/DeepROC_mix.png", "mix/Calibration_mix.png", "mix/DecisionCurve_mix.png"],
    ["inv/DeepROC_inv_1.png", "inv/Calibration_inv.png", "inv/DecisionCurve_inv.png"],
    ["noninv/DeepROC_noninv_1.png", "noninv/Calibration_noninv.png", "noninv/DecisionCurve_noninv.png"],
    ["baseline/DeepROC_baseline.png", "baseline/Calibration_baseline.png", "baseline/DecisionCurve_baseline.png"],
]

rows = []
for row in row_files:
    images = [cv2.imread(f"{base_dir}/{fname}") for fname in row]
    # Optionally resize images to same height
    min_height = min(img.shape[0] for img in images)
    resized = [cv2.resize(img, (int(img.shape[1]*min_height/img.shape[0]), min_height)) for img in images]
    row_img = cv2.hconcat(resized)
    rows.append(row_img)

# Now stack all rows vertically
min_width = min(row.shape[1] for row in rows)
rows_resized = [cv2.resize(row, (min_width, int(row.shape[0]*min_width/row.shape[1]))) for row in rows]
composite = cv2.vconcat(rows_resized)

cv2.imwrite(f"{base_dir}/composite_dense.png", composite, [cv2.IMWRITE_PNG_COMPRESSION, 9])