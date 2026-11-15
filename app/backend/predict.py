"""
The one common predict() function of the project (Member 3's integration duty).

predict(turbine_id, timestamp) returns everything the dashboard and any other consumer needs for one turbine at one time:
fused failure probability, risk band, the six model probabilities, sensor-deviation anomaly score, regime, days-to-failure estimate
and the top sensor drivers.

NOTE (honest scope): the scores come from the notebook pipeline's export (data/replay_scores_hourly.parquet). The trained models
themselves are in the notebook; this function serves their stored hourly scores. Scoring brand-new raw SCADA rows would need the
notebook's feature pipeline (normal-behaviour residuals) in front of the models.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd

DRIVER_RE = re.compile(r"^(.*?)\s*([+-]\d+(?:\.\d+)?)σ$")


def parse_drivers(text: str) -> list[dict]:
    out = []
    for part in str(text or "").split(";"):
        m = DRIVER_RE.match(part.strip())
        if m: out.append(dict(sensor=m.group(1).strip(), sigma=float(m.group(2))))
    return out


def _f(x, nd=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def predict(store, turbine_id: int, timestamp=None, now=None) -> dict:
    tb = store.by_tb.get(int(turbine_id))
    if tb is None: raise KeyError(f"unknown turbine {turbine_id}")
    t = pd.Timestamp(timestamp) if timestamp is not None else now
    if now is not None and t > now: raise ValueError("timestamp is later than the live clock - the future is not scored")
    i = int(np.searchsorted(tb["ts"].values, np.datetime64(t), side="right")) - 1
    if i < 0: raise ValueError("timestamp is before the first record")
    row = tb.iloc[i]
    lo = max(0, i - 24 * 7 + 1); win = tb.iloc[lo:i + 1]
    day = tb.iloc[max(0, i - 23):i + 1]
    thr = store.info
    rul = _f(row["rul_days_est"], 2) if row["band"] in ("Watch", "High") else None
    return dict(
        turbine_id=int(turbine_id), timestamp=str(row["ts"]), data_age_hours=_f((t - row["ts"]).total_seconds() / 3600, 1), regime=row["regime"], band=row["band"],
        risk_prob=_f(row["risk"]), risk_24h_max=_f(day["risk"].max()), risk_7d_max=_f(win["risk"].max()),
        thresholds=dict(watch=_f(thr["fused_watch_threshold"]), high=_f(thr["fused_high_threshold"])),
        model_probs=dict(gradient_boosting=_f(row["p_gradient_boosting"]), random_forest=_f(row["p_random_forest"]), logistic=_f(row["p_logistic"]),
                         bayes=_f(row["p_bayes"]), svm=_f(row["p_svm"]), ann=_f(row["p_ann"])),
        anomaly_score=_f(row["dev_norm"], 3), iforest_score=_f(row["anomaly_score"]),
        days_to_failure_est=rul, days_to_failure_mae=_f(store.tables["rul"].query("model == @thr['rul_model']")["test_mae_days"].mean() if len(store.tables["rul"]) else None, 2),
        top_drivers=parse_drivers(row["top_drivers"]),
        disclaimer=thr["disclaimer"])
