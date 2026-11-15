"""
WindGuard backend (FastAPI).  Start:  uvicorn backend.main:app --port 8000     (or: python run_all.py)
Docs (try every endpoint in the browser):  http://localhost:8000/docs
"""
from __future__ import annotations
import json
from contextlib import asynccontextmanager
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sklearn.metrics import roc_auc_score, average_precision_score

from .store import get_store, MODEL_COLS, MODEL_LABEL, HEALTH_SENSORS, SENSORS, REGIME_NAMES, TS
from .live import LiveClock
from .predict import predict as predict_fn, parse_drivers

S = None
CLOCK = None


@asynccontextmanager
async def lifespan(app):
    global S, CLOCK
    S = get_store()
    CLOCK = LiveClock(S.live_start, S.live_end)
    yield

app = FastAPI(title="WindGuard API", version="1.0", lifespan=lifespan,
              description="Live-replay failure-precursor scoring for wind-turbine SCADA. SIMULATION on synthetic data unless the notebook was run on real data.")


def rec(df: pd.DataFrame) -> list:
    return json.loads(df.to_json(orient="records", date_format="iso", double_precision=4))


def now(): return CLOCK.now()


def upto(tb, hours=None, t=None):
    t = t or now(); g = S.by_tb[int(tb)]
    j = int(np.searchsorted(g["ts"].values, np.datetime64(t), side="right"))
    i = 0 if hours is None else int(np.searchsorted(g["ts"].values, np.datetime64(t - pd.Timedelta(hours=hours)), side="right"))
    return g.iloc[i:j]


def check_tb(tb):
    if int(tb) not in S.by_tb: raise HTTPException(404, f"unknown turbine {tb}")


# ---------------------------------------------------------------------------------------------------------------------- meta / clock
@app.get("/health")
def health(): return dict(status="ok", turbines=S.turbines, rows=int(len(S.live)))


@app.get("/meta")
def meta():
    i = S.info
    return dict(run_info=i, turbines=S.turbines, regimes=REGIME_NAMES, sensors=SENSORS, health_sensors=HEALTH_SENSORS, models={k: MODEL_LABEL[k] for k in MODEL_COLS},
                thresholds=dict(watch=i["fused_watch_threshold"], high=i["fused_high_threshold"]), live_start=str(S.live_start), live_end=str(S.live_end))


@app.get("/live/state")
def live_state(): return CLOCK.state()


class Control(BaseModel):
    action: str                  # play | pause | speed | seek | reset | next_alert
    value: str | float | None = None


@app.post("/live/control")
def live_control(c: Control):
    if c.action == "next_alert":
        t = now(); a = S.alerts_all[S.alerts_all["start"] > t + pd.Timedelta(hours=12)]
        if len(a): return CLOCK.control("seek", a.iloc[0]["start"] - pd.Timedelta(hours=12))
        return CLOCK.state()
    if c.action not in ("play", "pause", "speed", "seek", "reset"): raise HTTPException(400, "unknown action")
    return CLOCK.control(c.action, c.value)


# ---------------------------------------------------------------------------------------------------------------------- common predict()
class PredictIn(BaseModel):
    turbine_id: int
    timestamp: str | None = None


@app.post("/predict")
def predict_post(p: PredictIn):
    try: return predict_fn(S, p.turbine_id, p.timestamp, now())
    except KeyError as e: raise HTTPException(404, str(e))
    except ValueError as e: raise HTTPException(400, str(e))


@app.get("/turbine/{tb}/risk")
def turbine_risk(tb: int):
    check_tb(tb)
    out = predict_fn(S, tb, None, now())
    g = upto(tb, 24 * 7)
    out["sparkline_7d"] = rec(g[["ts", "risk", "band"]].iloc[::3])
    # per-window risk = the highest hourly risk in each trailing window
    out["window_risk"] = {f"{h}h": round(float(upto(tb, h)["risk"].max()), 4) for h in (24, 72, 168)}
    return out


# ---------------------------------------------------------------------------------------------------------------------- alerts (needed by several pages)
def alert_table(t):
    a = S.alerts_all[S.alerts_all["start"] <= t].copy()
    a["last_seen"] = a["last"].clip(upper=t)
    def status(x):
        if pd.notna(x.t_fail) and x.t_fail <= t: return "Failure confirmed"
        if t <= x["last"] + pd.Timedelta(days=7): return "Open"
        return "False alarm"                       # 7 days passed after the alert ended and no failure followed
    a["status"] = a.apply(status, axis=1) if len(a) else ""
    a["lead_days"] = np.where(a["status"] == "Failure confirmed", a["lead_days"], np.nan)
    a["fault"] = np.where(a["status"] == "Failure confirmed", a["fault"], "")
    a["t_fail"] = a["t_fail"].where(a["status"] == "Failure confirmed")
    a["active"] = (t - a["last_seen"]) <= pd.Timedelta(hours=6)
    return a


@app.get("/alerts")
def alerts(limit: int = 50, only_active: bool = False):
    a = alert_table(now())
    if only_active: a = a[a["active"]]
    a = a.sort_values("start", ascending=False).head(limit)
    out = rec(a.drop(columns=["top_drivers"]))
    for o, d in zip(out, a["top_drivers"]): o["top_drivers"] = parse_drivers(d)
    return out


# ---------------------------------------------------------------------------------------------------------------------- 1. fleet overview
@app.get("/fleet/snapshot")
def fleet_snapshot():
    t = now(); rows = []
    for tb in S.turbines:
        g = upto(tb, 24 * 7)
        if not len(g): continue
        r = g.iloc[-1]
        completeness = float(g[SENSORS].notna().all(axis=1).tail(168).mean())
        day = g.tail(24)
        flat = int(sum(day[s].nunique() <= 1 for s in HEALTH_SENSORS)) if len(day) >= 12 else 0
        age = (t - r["ts"]).total_seconds() / 3600
        offline = age > 6                                   # no new data for 6 h: do not show a stale score as if it were live
        operating = "Offline (no data)" if offline or r["regime"] == "No data" else ("Idle (low wind)" if r["regime"] == REGIME_NAMES[0] else "Producing")
        rows.append(dict(turbine_id=tb, ts=str(r["ts"]), band="Offline" if offline else r["band"], offline=bool(offline), risk=float(r["risk"]), risk_24h_max=float(day["risk"].max()), regime=r["regime"], operating=operating,
                         wind=_n(r[SENSORS[0]]), power=_n(r[SENSORS[1]]), gear_oil=_n(r["Gear oil temperature (°C)"]), anomaly=float(r["dev_norm"]),
                         completeness=round(completeness, 3), flatlined_sensors=flat, age_hours=round(age, 1),
                         spark=[round(float(v), 4) for v in g["risk"].tail(72).iloc[::3]]))
    a = alert_table(t); win = S.live[(S.live["ts"] <= t) & (S.live["ts"] > t - pd.Timedelta(days=30))]
    reg = (win["regime"].value_counts(normalize=True) * 100).round(1).to_dict()
    fails = S.episodes[(S.episodes["t_fail"] <= t) & (S.episodes["t_fail"] >= S.live_start)]
    conf = a[a["status"] == "Failure confirmed"]
    rows_live = [r for r in rows if not r["offline"]]
    k = dict(turbines=len(rows), offline=len(rows) - len(rows_live), high=sum(r["band"] == "High" for r in rows_live), watch=sum(r["band"] == "Watch" for r in rows_live),
             fleet_risk_mean=round(float(np.mean([r["risk"] for r in rows_live])), 4) if rows_live else None, active_alerts=int(a["active"].sum()) if len(a) else 0,
             alerts_total=int(len(a)), failures_so_far=int(len(fails)), failures_warned=int(fails["t_fail"].apply(lambda x: ((conf["t_fail"] == x)).any()).sum()) if len(fails) else 0,
             false_alarms=int((a["status"] == "False alarm").sum()) if len(a) else 0,
             median_lead_days=_n(conf["lead_days"].median()) if len(conf) else None)
    return dict(sim_time=str(t), kpis=k, turbines=rows, regime_share=reg, regimes=REGIME_NAMES)


def _n(x): return None if pd.isna(x) else round(float(x), 3)


@app.get("/fleet/trend")
def fleet_trend(days: int = 60):
    t = now(); w = S.live[(S.live["ts"] <= t) & (S.live["ts"] > t - pd.Timedelta(days=days))].copy()
    w["day"] = w["ts"].dt.floor("D")
    d = w.groupby(["day", "turbine_id"])["risk"].max().reset_index(name="max_risk")
    f = w.groupby("day")["risk"].agg(mean_risk="mean", max_risk="max").reset_index()
    return dict(per_turbine=rec(d), fleet=rec(f))


# ---------------------------------------------------------------------------------------------------------------------- 6. turbine details
@app.get("/turbine/{tb}/series")
def turbine_series(tb: int, hours: int = 240):
    check_tb(tb); g = upto(tb, hours)
    cols = ["ts", "risk", "band", "regime", "dev_norm", "anomaly_score", "rul_days_est"] + SENSORS
    t = now(); ep = S.episodes[(S.episodes["turbine"] == tb) & (S.episodes["t_fail"] <= t) & (S.episodes["t_fail"] > t - pd.Timedelta(hours=hours))]
    z = rec(g[["ts"] + [f"z_{i}" for i in range(len(HEALTH_SENSORS))]].tail(1))
    return dict(series=rec(g[cols]), failures=rec(ep[["t_fail", "message"]]), latest_z={s: (z[0][f"z_{i}"] if z else None) for i, s in enumerate(HEALTH_SENSORS)})


@app.get("/turbine/{tb}/history")
def turbine_history(tb: int):
    """All failures of this turbine in the replayed year that have already happened, plus its alerts."""
    check_tb(tb); t = now(); a = alert_table(t); a = a[a["turbine_id"] == tb].sort_values("start", ascending=False)
    ep = S.episodes[(S.episodes["turbine"] == tb) & (S.episodes["t_fail"] <= t) & (S.episodes["t_fail"] >= S.live_start)]
    return dict(alerts=rec(a.drop(columns=["top_drivers"])), failures=rec(ep[["t_fail", "t_end", "message", "warned_watch", "warned_high"]]))


# ---------------------------------------------------------------------------------------------------------------------- 2. anomaly & alerts
@app.get("/anomaly/scatter")
def anomaly_scatter(turbine: int = 0, days: int = 45, max_points: int = 2500):
    t = now(); w = S.live[(S.live["ts"] <= t) & (S.live["ts"] > t - pd.Timedelta(days=days))]
    if turbine: w = w[w["turbine_id"] == turbine]
    hot = w[w["band"] != "Low"]; cold = w[w["band"] == "Low"]
    cold = cold.sample(min(len(cold), max(0, max_points - len(hot))), random_state=0) if len(cold) else cold
    d = pd.concat([cold, hot])[["ts", "turbine_id", "pc1", "pc2", "band", "regime", "dev_norm", "risk"]]
    return dict(points=rec(d), explained=[round(float(v), 3) for v in S.pca.explained_variance_ratio_[:2]], n_window=int(len(w)))


@app.get("/anomaly/timeline")
def anomaly_timeline(turbine: int, days: int = 30):
    check_tb(turbine); g = upto(turbine, days * 24)
    return rec(g[["ts", "dev_norm", "risk", "band", "regime"]])


@app.get("/anomaly/threshold")
def anomaly_threshold(value: float = 1.0):
    """Quality of the sensor-deviation anomaly score at a chosen threshold, on the whole test year (1.0 = 99th percentile of healthy 2021)."""
    L = S.live; y = L["target_any_fault"].values.astype(bool); f = (L["dev_norm"].values >= value)
    tp, fp, fn = int((f & y).sum()), int((f & ~y).sum()), int((~f & y).sum())
    prec = tp / max(tp + fp, 1); rec_ = tp / max(tp + fn, 1)
    caught = 0; n_ep = 0
    for e, g in L[L["episode_id"] >= 0].groupby("episode_id"):
        n_ep += 1; caught += int((g["dev_norm"] >= value).any())
    per_tb = L.assign(f=f).groupby("turbine_id")["f"].mean().mul(100).round(2).to_dict()
    return dict(threshold=value, flagged_pct=round(float(f.mean()) * 100, 2), precision=round(prec, 3), recall=round(rec_, 3), f1=round(2 * prec * rec_ / max(prec + rec_, 1e-9), 3),
                episodes=n_ep, episodes_caught=caught, flagged_pct_by_turbine={str(k): v for k, v in per_tb.items()},
                roc_auc=round(float(roc_auc_score(y, L["dev_norm"])), 3), pr_auc=round(float(average_precision_score(y, L["dev_norm"])), 3),
                iforest_roc_auc=round(float(roc_auc_score(y, L["anomaly_score"])), 3), base_rate=round(float(y.mean()), 4))


# ---------------------------------------------------------------------------------------------------------------------- 4. explainability
@app.get("/explain/global")
def explain_global():
    mc = S.tables["model_comparison"]
    cols = ["model", "family", "threshold", "pr_auc", "roc_auc", "precision", "recall", "f1", "episode_recall", "median_lead_days", "fa_per_turbine_year"]
    return dict(importance=rec(S.tables["importance"]), fusion=rec(S.tables["fusion"]), models=rec(mc[[c for c in cols if c in mc.columns]]))


@app.get("/explain/alert/{alert_id}")
def explain_alert(alert_id: int):
    a = S.alerts_all[S.alerts_all["alert_id"] == alert_id]
    if not len(a): raise HTTPException(404, "unknown alert")
    a = a.iloc[0]; g = S.by_tb[int(a["turbine_id"])]; r = g[g["ts"] == a["peak_ts"]].iloc[0]
    z = [dict(sensor=s, z=round(float(r[f"z_{i}"]), 2)) for i, s in enumerate(HEALTH_SENSORS)]
    return dict(alert_id=alert_id, turbine_id=int(a["turbine_id"]), peak_ts=str(a["peak_ts"]), peak_risk=float(a["peak_risk"]), band=a["band"], regime=r["regime"],
                drivers=parse_drivers(a["top_drivers"]), sensor_deviation=z,
                model_probs={MODEL_LABEL[k]: round(float(r[k]), 4) for k in MODEL_COLS})


# ---------------------------------------------------------------------------------------------------------------------- 5. validation & cross-farm
@app.get("/validation/curves")
def validation_curves(models: str = "risk,p_random_forest,p_gradient_boosting,p_logistic"):
    out = {}
    for m in [x for x in models.split(",") if x in MODEL_COLS]: out[MODEL_LABEL[m]] = S.curves(m)
    return out


@app.get("/validation/confusion")
def validation_confusion(model: str = "risk", threshold: float | None = None):
    if model not in MODEL_COLS: raise HTTPException(400, "unknown model")
    mc = S.tables["model_comparison"]
    row = mc[mc["column"] == model] if "column" in mc.columns else mc[mc["model"] == MODEL_COLS[model]]       # match by column name, fall back to model name
    default = float(S.info["fused_watch_threshold"]) if model == "risk" else (float(row["threshold"].iloc[0]) if len(row) else 0.2)
    thr = default if threshold is None else threshold
    L = S.live; y = L["target_any_fault"].values.astype(bool); f = L[model].values >= thr
    tp, fp, fn, tn = int((f & y).sum()), int((f & ~y).sum()), int((~f & y).sum()), int((~f & ~y).sum())
    p = tp / max(tp + fp, 1); r = tp / max(tp + fn, 1)
    return dict(model=MODEL_LABEL[model], threshold=thr, default_threshold=default, tp=tp, fp=fp, fn=fn, tn=tn, precision=round(p, 3), recall=round(r, 3),
                specificity=round(tn / max(tn + fp, 1), 3), f1=round(2 * p * r / max(p + r, 1e-9), 3), rows=int(len(L)),
                note="Counts are on hourly replay rows; the notebook's table uses every 10-minute row, so rates agree but counts differ.")


@app.get("/validation/summary")
def validation_summary():
    ep = S.episodes[S.episodes["t_fail"].dt.year == S.info["test_year"]]
    a = S.alerts_all; conf = a[a["t_fail"].notna()]
    return dict(ci=rec(S.tables["ci"]), cv=rec(S.tables["cv"]), crossfarm=rec(S.tables["crossfarm"]), fault_kind=rec(S.tables["fault_kind"]), rul=rec(S.tables["rul"]),
                episodes=rec(ep[["turbine", "message", "t_fail", "warned_watch", "warned_high"]]), lead_days=[round(float(x), 2) for x in conf["lead_days"].dropna()],
                alerts_total=int(len(a)), alerts_false=int(a["t_fail"].isna().sum()))
