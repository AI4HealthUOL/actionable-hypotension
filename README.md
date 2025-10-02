# Predicting Catecholamine Therapy Initiation

Repository with datasets and models from our paper: *"Towards actionable hypotension prediction: Predicting catecholamine therapy initiation in the intensive care unit"*.

## Setup

1. **Clone this repository**

   ```bash
   git clone https://github.com/AI4HealthUOL/predicting-catecholamine-therapy-initiation.git
   cd predicting-catecholamine-therapy-initiation
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Install project modules (editable / dev mode)**

   ```bash
   pip install -e .
   ```

4. **Set up MIMIC-III in Postgres**<br>
   Follow the official [MIT-LCP buildmimic/postgres instructions](https://github.com/MIT-LCP/mimic-code/tree/main/mimic-iii/buildmimic/postgres).

   > These instructions also cover how to **download the MIMIC-III CSVs from PhysioNet** and load them into Postgres.

5. **Configure database connection**<br>
   Copy the env template `.env.example` → `.env` and set **exactly one** `DATABASE_URI` (no quotes):

   ```bash
   cp .env.example .env
   ```

   Example:

   ```
   DATABASE_URI=postgresql+psycopg2://USERNAME:PASSWORD@HOST:PORT/DBNAME
   ```

## Usage

* To try pre-trained models → run **1** and **3**.
* To retrain models → run **1, 2, 3**.

### 1. Prepare Datasets

Run the SQL files in order:

* **patient_metadata**

  * `all_mv_icu_stays.sql`
  * `chartevents_metadata.sql`
  * `mv_metadata_binned.sql`
  * `mv_drug_item_map.sql`

* **context_windows**

  * `linkorder_treatment_events.sql`
  * `additional_meds_in_windows.sql`
  * `all_mv_context_target_windows.sql`
  * `all_mv_labeled_windows.sql`

* **map_values**

  * `all_mv_labeled_windows_with_map_values.sql`
  * `invasive_noninvasive_mix_windows.sql`
  * `<datasetname>_statistical_features.sql`

* **split_data**

  * `split_all_subjects.sql`

* **merge_final_datasets**

  * `dataset_inv_ninv_mix.sql`

### 2. Train and Calibrate Models (skip if using pretrained models)

* **XGBoost:**

  * Train: `training/train_xgboost_models.ipynb`
  * Calibrate: `calibration/calibrate_xgboost_models.ipynb` (set model name in marked cell)

* **Baseline:**

  * Train & Calibrate: `baseline_model/train_and_calibrate_baseline_model.ipynb`

### 3. Evaluate Models

> In each script you need to set the model name in the marked cell.

* **Performance plots:** `ce_approach/evaluation/evaluate_models.ipynb`
* **DeepROC:**

  * Precompute: `ce_approach/evaluation/deeproc_cli.py` (⚠ long runtime)
  * Plot: `ce_approach/evaluation/deeproc_plot.ipynb`
* **Metric tables:** `ce_approach/evaluation/calculate_tables.ipynb`
* **Subgroup analysis:**

  * Precompute: `subanalysis/notebooks/create_test_full.ipynb`
  * Create Table: `subanalysis/notebooks/subgroup_analysis.ipynb`
