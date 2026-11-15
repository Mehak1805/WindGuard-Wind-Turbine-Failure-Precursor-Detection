"""
Data layer of the WindGuard backend.

Reads the files exported by the notebook (data/), adds three things the dashboard needs
(regime, PCA sensor-deviation anomaly score, alert events) and writes the shared "outputs/" files
(data contract: turbine_id, timestamp, regime + the model's own columns).

Everything here is computed once at start-up; the API only slices these tables.
"""
from __future__ import annotations
import json, os, re
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import roc_curve, precision_recall_curve, roc_auc_score, average_precision_score

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.environ.get("WINDGUARD_DATA", os.path.join(ROOT, "data"))
OUT = os.environ.get("WINDGUARD_OUT", os.path.join(ROOT, "outputs"))

TS = "Date and time"
WIND, POWER, AMB = "Wind speed (m/s)", "Power (kW)", "Nacelle ambient temperature (°C)"
SENSORS = [WIND, POWER, AMB, "Gear oil temperature (°C)", "Front bearing temperature (°C)",
           "Generator bearing front temperature (°C)", "Stator temperature 1 (°C)",
           "Gear oil inlet pressure (bar)", "Hydraulic oil pressure (bar)"]
HEALTH_SENSORS = SENSORS[3:]            # sensors that describe machine condition (not operating conditions)
REGIME_NAMES = ["Idle / low wind", "Partial load", "High load", "Rated power"]   # sorted by mean power

# model column in the replay table -> row in model_comparison_2022.csv
MODEL_COLS = {
    "risk": "WindGuard fused risk score",
    "p_random_forest": "Random Forest",
    "p_gradient_boosting": "Gradient Boosting",
    "p_ann": "ANN (64-32 MLP)",
    "p_logistic": "Logistic Regression (L2)",
    "p_svm": "SVM (RBF approx., Platt)",
    "p_bayes": "Gaussian Naive Bayes (ML, Platt)",
}
MODEL_LABEL = {"risk": "Fused risk score", "p_random_forest": "Random Forest", "p_gradient_boosting": "Gradient Boosting",
               "p_ann": "ANN", "p_logistic": "Logistic Regression", "p_svm": "SVM", "p_bayes": "Bayesian (GNB)"}


def _csv(name):
    p = os.path.join(DATA, name)
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


class Store:
    def __init__(self):
        self.info = json.load(open(os.path.join(DATA, "run_info.json")))
        r = pd.read_parquet(os.path.join(DATA, "replay_scores_hourly.parquet"))
        r = r.rename(columns={TS: "ts", "turbine": "turbine_id"}).sort_values(["turbine_id", "ts"]).reset_index(drop=True)
        r["ts"] = pd.to_datetime(r["ts"])
        self.all = r
        self._add_regime_and_anomaly()
        self.live = self.all[self.all["split"] == "test"].reset_index(drop=True)      # the replayed "live" year (never used for fitting)
        self.live_start, self.live_end = self.live["ts"].min(), self.live["ts"].max()
        self.turbines = sorted(self.live["turbine_id"].unique().tolist())
        self.by_tb = {int(t): g.reset_index(drop=True) for t, g in self.live.groupby("turbine_id")}
        ep = _csv("episodes.csv")
        ep["t_fail"] = pd.to_datetime(ep["t_fail"]); ep["t_end"] = pd.to_datetime(ep["t_end"])
        self.episodes = ep
        self.tables = {n: _csv(f + ".csv") for n, f in dict(model_comparison="model_comparison_2022", importance="feature_importance", fusion="fusion_weights",
                       cv="cv_summary", ci="bootstrap_ci_2022", crossfarm="cross_farm_results", fault_kind="cross_farm_by_fault_kind", rul="rul_results").items()}
        self.alerts_all = self._build_alerts()
        self._curves = {}
        self.write_outputs()

    # ------------------------------------------------------------------------------------------------------------
    def _add_regime_and_anomaly(self):
        r = self.all
        ok = r[[WIND, POWER]].notna().all(axis=1)
        km = KMeans(4, n_init=5, random_state=0).fit(r.loc[ok, [WIND, POWER]].sample(min(30000, int(ok.sum())), random_state=0))
        order = np.argsort(km.cluster_centers_[:, 1])                         # clusters sorted by mean power
        rank = {int(c): i for i, c in enumerate(order)}
        r["regime_id"] = -1
        r.loc[ok, "regime_id"] = [rank[int(c)] for c in km.predict(r.loc[ok, [WIND, POWER]])]
        r["regime"] = r["regime_id"].map(dict(enumerate(REGIME_NAMES))).fillna("No data")
        self.kmeans, self.regime_rank = km, rank

        # sensor deviation z-scores: each turbine + regime is compared with its own healthy 2021 behaviour (robust median / IQR)
        healthy = r[(r["split"] == "val") & (r["target_any_fault"] == 0)]
        key = pd.MultiIndex.from_frame(r[["turbine_id", "regime_id"]])
        Z = pd.DataFrame(index=r.index)
        for s in HEALTH_SENSORS:
            g = healthy.groupby(["turbine_id", "regime_id"])[s]
            med, scale = g.median(), (g.quantile(.75) - g.quantile(.25)) / 1.349
            Z[s] = (r[s].values - med.reindex(key).values) / np.maximum(scale.reindex(key).values, 1e-3)
        Z = Z.clip(-8, 8).fillna(0.0)
        self.z = Z
        hm = ((r["split"] == "val") & (r["target_any_fault"] == 0)).values
        self.pca = PCA(n_components=3).fit(Z.values[hm])
        P = self.pca.transform(Z.values)
        r["pc1"], r["pc2"] = P[:, 0].astype("float32"), P[:, 1].astype("float32")
        rec = np.linalg.norm(Z.values - self.pca.inverse_transform(P), axis=1)
        r["dev_score"] = rec.astype("float32")                               # PCA reconstruction error of the regime-normalised sensors
        thr_ref = np.quantile(rec[hm], 0.99)
        r["dev_norm"] = (r["dev_score"] / thr_ref).astype("float32")         # 1.0 = the 99th percentile of healthy 2021
        for i, s in enumerate(HEALTH_SENSORS): r[f"z_{i}"] = Z[s].values.astype("float32")

    # ------------------------------------------------------------------------------------------------------------
    def _build_alerts(self):
        """Group consecutive Watch/High hours (gap <= 24 h) into alert events, per turbine."""
        L, rows = self.live, []
        flagged = L[L["band"].isin(["Watch", "High"])]
        for tb, g in flagged.groupby("turbine_id"):
            t = g["ts"].values; new = np.r_[True, np.diff(t) > np.timedelta64(24, "h")]
            for k, part in g.groupby(np.cumsum(new)):
                pk = part.loc[part["risk"].idxmax()]
                rows.append(dict(turbine_id=int(tb), start=part["ts"].min(), last=part["ts"].max(), peak_ts=pk["ts"], peak_risk=float(pk["risk"]),
                                 band="High" if (part["band"] == "High").any() else "Watch", hours=int(len(part)), top_drivers=str(pk["top_drivers"])))
        a = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)
        a["alert_id"] = a.index
        fail, lead, msg = [], [], []
        for _, x in a.iterrows():                                            # does a real failure follow within 7 days (ground truth, only used for evaluation)?
            e = self.episodes
            m = e[(e["turbine"] == x.turbine_id) & (e["t_fail"] >= x.start) & (e["t_fail"] <= x["last"] + pd.Timedelta(days=7))]
            if len(m):
                m = m.iloc[0]; fail.append(m["t_fail"]); lead.append((m["t_fail"] - x.start).total_seconds() / 86400); msg.append(m["message"])
            else: fail.append(pd.NaT); lead.append(np.nan); msg.append("")
        a["t_fail"], a["lead_days"], a["fault"] = fail, lead, msg
        return a

    # ------------------------------------------------------------------------------------------------------------
    def write_outputs(self):
        """Data contract: turbine_id, timestamp, regime + the model's own columns. Dashboard / other members read these files."""
        os.makedirs(OUT, exist_ok=True)
        a = self.all
        a[["turbine_id", "ts", "regime", "risk", "band", "p_gradient_boosting", "p_random_forest", "p_logistic", "p_bayes", "p_svm", "p_ann", "rul_days_est"]] \
            .rename(columns={"ts": "timestamp", "risk": "risk_prob"}).to_csv(os.path.join(OUT, "risk_scores.csv"), index=False)
        a[["turbine_id", "ts", "regime", "anomaly_score", "dev_score", "pc1", "pc2"]].rename(columns={"ts": "timestamp", "anomaly_score": "iforest_score",
            "dev_score": "anomaly_score"}).to_csv(os.path.join(OUT, "anomaly_scores.csv"), index=False)

    # ------------------------------------------------------------------------------------------------------------
    def curves(self, col):
        """ROC and PR curve of one model on the test year (cached, ≤ 250 points)."""
        if col in self._curves: return self._curves[col]
        t = self.live
        y, p = t["target_any_fault"].values, t[col].values
        fpr, tpr, _ = roc_curve(y, p); pr, rc, _ = precision_recall_curve(y, p)
        ix = np.unique(np.linspace(0, len(fpr) - 1, 250).astype(int)); jx = np.unique(np.linspace(0, len(pr) - 1, 250).astype(int))
        out = dict(roc=dict(fpr=fpr[ix].round(4).tolist(), tpr=tpr[ix].round(4).tolist()), pr=dict(recall=rc[jx].round(4).tolist(), precision=pr[jx].round(4).tolist()),
                   roc_auc=float(roc_auc_score(y, p)), pr_auc=float(average_precision_score(y, p)))
        self._curves[col] = out
        return out


_STORE: Store | None = None
def get_store() -> Store:
    global _STORE
    if _STORE is None: _STORE = Store()
    return _STORE
