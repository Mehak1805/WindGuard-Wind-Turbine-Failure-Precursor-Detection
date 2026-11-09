## WindGuard: 5-Member One-Month Work Division

Group-4 ML course project: wind turbine failure precursor detection from SCADA sensor data. Every member gets an equal ML share and an equal dashboard share.

## Timeline note

The plan is written as four weeks, where Week 4 is integration, report and demo. If the deadline is Oct 31, only about three weeks remain from Oct 10. In that case run Week 4 alongside Week 3 and cut the stretch items, marked with ★.

## How the split works

Each member owns one ML stage end to end, the Streamlit page that shows it, and one shared integration duty. Nobody is only the dashboard person or only the report person.

| Member ML ownership |   | Dashboard page | Integration duty |
| --- | --- | --- | --- |
| Member | Data prep, labelling, EDA, | Fleet Overview: turbine | Shared data loader, |
| 1 | K-Means regimes (★ | status, regimes, data | repo and README |
|   | DBSCAN/BIRCH | health |   |
|   | comparison) |   |   |
| Member | Feature engineering, PCA | Anomaly & Alerts: PCA | App shell, navigation, |
| 2 | (★ Kernel PCA), anomaly | scatter, anomaly | styling |
|   | detection | timeline, threshold slider |   |
| Member | Logistic Regression, SVM, | Turbine Risk: failure | Model packaging with |
| 3 | Bayesian classifier | probability per turbine | one common predict() |
|   |   | and window | function |
| Member | Random Forest, Gradient | Explainability: top | Report assembly and |
| 4 | Boosting, feature | drivers per flag, model | literature review |
|   | importance (★ small | comparison | polish |
|   | ANN) |   |   |


| Member ML ownership |   | Dashboard page | Integration duty |
| --- | --- | --- | --- |
| Member | Validation (CV, ROC-AUC, | Validation & Cross-Farm: | Demo script, final QA, |
| 5 | bootstrap CI), cross-farm | ROC, confusion matrix, | viva prep |
|   | test (★ RUL regression) | Kelmarsh to |   |
|   |   | Penmanshiel drop |   |

## Ground rules so nobody blocks anyone

- Data contract: every ML member writes outputs to outputs/ with turbine_id , timestamp , regime plus their own columns (for example anomaly_score , risk_prob ). Dashboard pages only read those files.

- Sample data by Day 3: Member 1 ships a small cleaned dataset so everyone models on Day 4 instead of waiting for the full pipeline.

- One evaluation setup: Member 5 shares the chronological split and metric functions by Day 4, and everyone uses them.

## Week 1: Foundation

Everyone has a working baseline on sample data and a stub page with mock data.

- Member 1: download Kelmarsh and Penmanshiel, align the event log, fix the pre-failure label rule, ship the sample (Day 3), start EDA. Page: Fleet Overview wireframe.

- Member 2: window features and power-curve deviation on the sample. Page: app shell, navigation, theme.

- Member 3: Logistic Regression baseline. Page: Risk stub.

- Member 4: Random Forest baseline. Page: Explainability stub.

- Member 5: chronological split and metric functions for the whole team. Page: Validation stub.

## Week 2: Core models on full data

Each page goes live with real outputs.

- Member 1: full-data pipeline, K-Means regimes, label check against the EDP logbook. Page: Fleet Overview live.


- Member 2: PCA with component selection, Isolation Forest or density anomaly per regime. Page: Anomaly live.

- Member 3: tuned Logistic Regression and SVM, class weights and SMOTE inside training folds only. Page: Risk live.

- Member 4: tuned Random Forest and Gradient Boosting, feature importance. Page: Explainability live.

- Member 5: CV, ROC-AUC and bootstrap CI on each model as it lands. Page: Validation with Kelmarsh results.

## Week 3: Advanced pieces and cross-farm

Feature freeze at the end of this week.

- Member 1: ★ DBSCAN/BIRCH comparison, Penmanshiel prepared on the shared channels. Page: filters and polish.

- Member 2: ★ Kernel PCA, anomaly threshold tuning, alert list. Page: threshold slider.

- Member 3: Bayesian classifier with calibrated probabilities, model packaging. Page: probability gauge, per-window risk.

- Member 4: ★ small ANN comparison, per-flag top-driver explanations. Page: model comparison view.

- Member 5: cross-farm test (train Kelmarsh, test Penmanshiel), ★ RUL regression. Page: cross-farm and days-to-failure views.

## Week 4: Integration, report, demo

No new modelling.

- Everyone: wire the pages into one app and run the full demo end to end.

- Member 1: final README, data section of the report, check that a fresh clone runs.

- Member 2: consistency pass on the UI and screenshots for the report.

- Member 3: write-up for the classification and Bayesian results.

- Member 4: assemble the report and results tables.

- Member 5: demo script, test cases, viva Q&A.


## Viva readiness

Each member should be able to explain their stage: what it does, why it was chosen, what the result means and where it fails.

## Follow-up on the report

If the ★ items are cut, the methodology and deliverables sections of the WindGuard report need a matching edit. The existing Section 6 of the report also uses a different division and should be replaced with this one.
