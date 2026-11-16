# WindGuard - end-to-end dashboard (backend + frontend)

    app/
    ├── run_all.py            <- starts everything (python run_all.py)
    ├── requirements.txt
    ├── backend/              FastAPI service: data layer, common predict(), live-replay clock
    │   ├── main.py           REST endpoints  (docs at http://localhost:8000/docs)
    │   ├── store.py          loads data/, adds regimes + PCA anomaly score + alert events, writes outputs/
    │   ├── predict.py        the ONE common predict(turbine_id, timestamp)
    │   └── live.py           replay clock (play / pause / speed / jump to next alert)
    ├── frontend/             Streamlit dashboard (only talks to the backend over HTTP)
    │   ├── app.py            navigation + live-clock sidebar
    │   ├── api.py, ui.py     API client, theme, shared widgets
    │   ├── views/            the six pages: fleet, anomaly, risk, explain, validation, turbine
    │   ├── assets/           (optional) put hero.jpg here for a photo banner on Fleet Overview

    ├── .streamlit/config.toml  (theme)
    ├── data/                 the notebook's exported results (replay_scores_hourly.parquet, *.csv, run_info.json)
    └── outputs/              data contract files written by the backend: risk_scores.csv, anomaly_scores.csv

## Run (VS Code terminal, inside this folder)
    python -m venv .venv
    .venv\Scripts\activate            (Mac/Linux: source .venv/bin/activate)
    pip install -r requirements.txt
    python run_all.py

Dashboard: http://localhost:8501   ·   API docs: http://localhost:8000/docs

## How "real time" works
The backend replays the 2022 test year as if it were arriving now (default 12 simulated hours per second). The sidebar
controls the clock; every page asks the backend "what is true at the current replay time?" and refreshes every few seconds.
Outcomes (failure confirmed / false alarm) only use information available at the replay time - the future is never shown.

## Where the data comes from
`data/` holds the files exported by the notebook (`notebooks/WindGuard_complete_proj.ipynb`, last section "9. Dashboard Export"), so the notebook,
the report and the dashboard show the same numbers. To refresh the dashboard after re-running the notebook: copy the files from
`outputs/dashboard_export/` into `app/data/` and restart (`python run_all.py`).

## The pages
Fleet Overview · Anomaly & Alerts · Turbine Risk · Explainability & Models · Validation & Cross-Farm · Turbine Details.
Every number comes from the notebook export or from the backend's calculations on it; nothing is invented for display.

## Honest scope
* The fleet pages cover the 6 Kelmarsh turbines (the only farm with hourly scores). Penmanshiel appears on *Validation & Cross-Farm* only.
* **Data origin is unconfirmed:** the CSV headers say "-like" and the ground-truth files hold simulation parameters, so these results show the
  workflow, not proven performance on real turbines. The same note is shown on every page.
* `predict()` serves the hourly scores the notebook computed; it does not score brand-new raw SCADA rows (that would need the notebook's
  feature pipeline in front of the models).
* The fused risk is a plain average of Logistic Regression, Random Forest and Gradient Boosting probabilities. The Isolation Forest is weak;
  the Anomaly page therefore also shows a PCA sensor-deviation score.
* The test year has only 13 failures, so every interval is wide, and about 5-6 false alarms per turbine-year remain at the chosen threshold.
