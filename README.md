# WindGuard-Wind-Turbine-Failure-Precursor-Detection

A classical machine-learning pipeline that looks for **failure precursors in wind turbines using only routine SCADA sensor data**. It flags a turbine that is heading toward a component failure early enough for maintenance to be planned, and shows which sensor readings and operating regime are driving the flag. No new hardware is needed.

Built as the ML course project by **Group-4**: Dhruv, Aditya Pathak, Anshika, Manya Awasthi, Mehak Kumar.

> **Scope note:** WindGuard is decision support for scheduling inspections. It does not control or shut down a turbine, and it is tested only against historical SCADA and event data from real turbines.

---

## Problem

Wind turbines are usually serviced on a fixed calendar schedule instead of by actual condition. Healthy turbines get inspected for nothing, while real faults in the gearbox, generator or hydraulic system can develop between inspections and only show up after an unplanned shutdown. Many existing condition-monitoring tools are vendor-locked, and many published studies test on a single farm only.

## Objective

Predict, from a turbine's recent SCADA window, whether it is heading toward a component failure early enough for proactive maintenance, and identify which sensor readings and operating regime drive that prediction.

## Approach

| Stage | Technique |
|---|---|
| Data preparation | Align SCADA with the fault/event log, label the N-day window before each failure as pre-failure, handle missing values |
| EDA | Distributions, trends, correlations, failure frequency |
| Feature engineering | Per-channel mean, standard deviation, trend slope, plus a power-curve-deviation feature |
| Dimensionality reduction | PCA / Kernel PCA on the ~99 correlated sensor features |
| Regime clustering | K-Means (DBSCAN and BIRCH compared) to group operating regimes |
| Anomaly detection | Density estimation / Isolation Forest fitted on normal windows |
| Baseline classification | Logistic Regression, SVM |
| Bayesian classification | Bayes' Rule with Maximum-Likelihood estimation for probability scores |
| Ensembles | Random Forest, Gradient Boosting, plus a small ANN for comparison |
| RUL regression | Linear, Ridge, Lasso (only where event history supports a target) |
| Validation | Stratified cross-validation, confusion matrix, ROC-AUC, bootstrap CIs |
| Cross-farm test | Train on Kelmarsh, test on Penmanshiel without retraining |
| Deployment | Streamlit decision-support dashboard |

Because failures are rare, accuracy alone is not used. Precision, recall, F1, ROC-AUC and the confusion matrix are reported together.

## Datasets

The data is not stored in this repo. Download it and place it under `data/raw/`.

| Dataset | Use | Link |
|---|---|---|
| Kelmarsh Wind Farm | Primary, model development (6 turbines, 2016 to 2024, ~99 variables, event log) | https://zenodo.org/records/16807551 |
| Penmanshiel Wind Farm | Independent cross-farm test (14 turbines, 150+ variables) | https://zenodo.org/records/16807304 |
| EDP Wind Farm 1 (Mendeley mirror) | Backup, includes a 28-event failure logbook | https://data.mendeley.com/datasets/zjxjnjp3xs/1 |

Check the licence and citation details on each record and credit the data providers in any write-up.

## Repository structure

```
WindGuard/
├── data/
│   ├── raw/                # downloaded datasets (git-ignored)
│   └── processed/          # cleaned and windowed data (git-ignored)
├── notebooks/
│   ├── 01_data_prep_eda.ipynb
│   ├── 02_features_pca_clustering.ipynb
│   ├── 03_anomaly_detection.ipynb
│   ├── 04_classification_bayesian.ipynb
│   ├── 05_ensemble_rul.ipynb
│   └── 06_validation_cross_farm.ipynb
├── src/                    # reusable pipeline code
├── app/                    # Streamlit dashboard
├── reports/                # final report and slides
├── requirements.txt
└── README.md
```

## Setup

```bash
git clone https://github.com/Mehak1805/WindGuard.git
cd WindGuard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Suggested `requirements.txt`:

```
numpy
pandas
scipy
scikit-learn
imbalanced-learn
matplotlib
seaborn
streamlit
jupyter
```

Then download the datasets into `data/raw/kelmarsh/` and `data/raw/penmanshiel/` and run the notebooks in order.


## Status

Work in progress. Results and metrics will be added here once the validation phase is complete.

## Limitations

- Failure labels come from event logs and may be sparse or noisy, so label quality is checked first.
- Failures are rare, so class imbalance is handled with class weights and SMOTE/ADASYN inside training folds only.
- Kelmarsh and Penmanshiel use different turbine models and sensor sets, so cross-farm results use only the shared channels.
- Splits are chronological and by turbine to avoid temporal leakage.

## Acknowledgements

SCADA data from the Kelmarsh and Penmanshiel wind farms (Zenodo) and the EDP open data release (Mendeley mirror).
