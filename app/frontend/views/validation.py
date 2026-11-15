"""Page 5 - Validation & Cross-Farm: ROC / PR curves, confusion matrix with threshold slider, CV, bootstrap CI, Kelmarsh -> Penmanshiel drop."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Validation & Cross-Farm")
meta = api.get("/meta")
ui.hero("Validation & Cross-Farm", "Honest evaluation: chronological split (train 2016-20, validate 2021, test 2022), cross-validation, bootstrap intervals and a test on a second farm.")
v = api.get("/validation/summary")
ci = pd.DataFrame(v["ci"])

fused = ci[ci["model"].str.contains("fused", case=False)]
row = fused.iloc[0] if len(fused) else ci[ci["model"] == "Random Forest"].iloc[0]
c = st.columns(5)
conf0 = api.get("/validation/confusion", model="risk")
ui.kpi(c[0], "Precision", f"{conf0['precision']:.2f}", "fused risk · Watch threshold")
ui.kpi(c[1], "Recall", f"{conf0['recall']:.2f}", "pre-failure hours flagged")
ui.kpi(c[2], "ROC-AUC", str(row["roc_auc"]).split(" ")[0], "95% CI " + str(row["roc_auc"]).split(" ", 1)[1] if " " in str(row["roc_auc"]) else "")
ui.kpi(c[3], "PR-AUC", str(row["pr_auc"]).split(" ")[0], "95% CI " + str(row["pr_auc"]).split(" ", 1)[1] if " " in str(row["pr_auc"]) else "")
n_ep = len(v["episodes"]); caught = int(pd.DataFrame(v["episodes"])["warned_watch"].fillna(0).sum())
ui.kpi(c[4], "Failures warned", f"{caught} / {n_ep}", f"test year · {v['alerts_false']} of {v['alerts_total']} alerts had no failure")

st.markdown("#### ROC and precision-recall curves (test year)")
models = {"Fused risk score": "risk", "Random Forest": "p_random_forest", "Gradient Boosting": "p_gradient_boosting", "Logistic Regression": "p_logistic", "SVM": "p_svm", "ANN": "p_ann", "Bayesian (GNB)": "p_bayes"}
sel = st.multiselect("Models (up to 5 stay readable)", list(models), default=["Fused risk score", "Random Forest", "Gradient Boosting", "Logistic Regression"], max_selections=6)
if sel:
    cv = api.get("/validation/curves", models=",".join(models[s] for s in sel))
    roc = pd.concat([pd.DataFrame(dict(fpr=x["roc"]["fpr"], tpr=x["roc"]["tpr"], model=f"{k} ({x['roc_auc']:.2f})")) for k, x in cv.items()])
    prc = pd.concat([pd.DataFrame(dict(recall=x["pr"]["recall"], precision=x["pr"]["precision"], model=f"{k} ({x['pr_auc']:.2f})")) for k, x in cv.items()])
    colr = alt.Color("model:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(title="model (AUC)", orient="bottom", columns=2))
    a, b = st.columns(2)
    diag = alt.Chart(pd.DataFrame(dict(x=[0, 1], y=[0, 1]))).mark_line(strokeDash=[4, 4], color=ui.MUTED).encode(x="x:Q", y="y:Q")
    with a:
        ui.show(alt.Chart(roc).mark_line(strokeWidth=2).encode(x=alt.X("fpr:Q", title="false-positive rate"), y=alt.Y("tpr:Q", title="true-positive rate"), color=colr, tooltip=["model", "fpr", "tpr"]) + diag, 300)
    with b:
        ui.show(alt.Chart(prc).mark_line(strokeWidth=2).encode(x=alt.X("recall:Q"), y=alt.Y("precision:Q", scale=alt.Scale(domain=[0, 1])), color=colr, tooltip=["model", "recall", "precision"]), 300)

st.markdown("#### Confusion matrix – move the alert threshold")
a, b = st.columns([1, 1.2])
with a:
    mname = st.selectbox("Model", list(models), index=0)
    base = api.get("/validation/confusion", model=models[mname])
    thr = st.slider("Threshold", 0.01, 0.99, float(min(max(base["default_threshold"], 0.01), 0.99)), 0.01)
    cm = api.get("/validation/confusion", model=models[mname], threshold=thr)
    m = st.columns(4)
    m[0].metric("Precision", f"{cm['precision']:.2f}"); m[1].metric("Recall", f"{cm['recall']:.2f}"); m[2].metric("F1", f"{cm['f1']:.2f}"); m[3].metric("Specificity", f"{cm['specificity']:.3f}")
    st.caption(cm["note"])
with b:
    grid = pd.DataFrame([dict(actual="Pre-failure", pred="Alert", n=cm["tp"], what="caught"), dict(actual="Pre-failure", pred="No alert", n=cm["fn"], what="missed"),
                         dict(actual="Healthy", pred="Alert", n=cm["fp"], what="false alarm"), dict(actual="Healthy", pred="No alert", n=cm["tn"], what="correctly quiet")])
    h = alt.Chart(grid).mark_rect(stroke="#ffffff", strokeWidth=3, cornerRadius=6).encode(x=alt.X("pred:N", title="model says", sort=["Alert", "No alert"], axis=alt.Axis(labelAngle=0)),
                                                                                         y=alt.Y("actual:N", title="reality", sort=["Pre-failure", "Healthy"]),
                                                                                         color=alt.Color("n:Q", scale=alt.Scale(scheme="blues", type="sqrt"), legend=None), tooltip=["actual", "pred", "what", "n"])
    t = alt.Chart(grid).mark_text(fontSize=18, fontWeight="bold").encode(x=alt.X("pred:N", sort=["Alert", "No alert"]), y=alt.Y("actual:N", sort=["Pre-failure", "Healthy"]), text=alt.Text("n:Q", format=","),
                                                                        color=alt.condition(alt.datum.n > cm["tn"] * 0.2, alt.value("white"), alt.value(ui.INK)))
    ui.show(h + t, 260)

st.markdown("#### Cross-validation and bootstrap intervals")
l, r = st.columns(2)
with l:
    cvd = pd.DataFrame(v["cv"]); cvd["lo"] = cvd["pr_auc_mean"] - cvd["pr_auc_sd"]; cvd["hi"] = cvd["pr_auc_mean"] + cvd["pr_auc_sd"]
    bar = alt.Chart(cvd).mark_bar(color=ui.BRAND, cornerRadiusEnd=3).encode(y=alt.Y("model:N", sort="-x", title=None), x=alt.X("pr_auc_mean:Q", title="PR-AUC, 5-fold grouped CV (± 1 sd)", scale=alt.Scale(domain=[0, 1])))
    err = alt.Chart(cvd).mark_rule(color=ui.INK).encode(y="model:N", x="lo:Q", x2="hi:Q")
    ui.show(bar + err, 200)
    st.caption("Folds are grouped by turbine-week so neighbouring hours never sit on both sides of a split.")
with r:
    st.dataframe(ci.rename(columns={"model": "Model", "episode_recall": "Failures caught"}), hide_index=True, width="stretch")
    st.caption("Block bootstrap by turbine-week, 95% intervals. With only 14 failures in the test year the intervals are wide – read them, not just the point values.")

st.markdown("#### Kelmarsh → Penmanshiel: how much is lost on a second farm?")
cf = pd.DataFrame(v["crossfarm"])
gb = cf[cf["model"] == "Gradient Boosting"].copy()
gb["setting"] = gb["farm"].where(gb["farm"].str.contains("in-farm"), gb["farm"] + " · " + gb["normalisation"].str.split("(").str[0].str.strip())
long = gb.melt(id_vars="setting", value_vars=["pr_auc", "roc_auc", "precision", "recall"], var_name="metric", value_name="value")
ch = alt.Chart(long).mark_bar(cornerRadiusEnd=3).encode(x=alt.X("metric:N", title=None, axis=alt.Axis(labelAngle=0)), xOffset="setting:N", y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1]), title=None),
                                                         color=alt.Color("setting:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(orient="bottom", columns=1, title=None, labelLimit=420)), tooltip=["setting", "metric", alt.Tooltip("value:Q", format=".2f")])
x, y = st.columns([3, 2])
with x:
    ui.show(ch, 320)
with y:
    inf = gb[gb["farm"].str.contains("in-farm")].iloc[0]; adapt = gb[gb["normalisation"].str.contains("per-farm")].iloc[0]
    st.metric("Precision drop on the other farm", f"{adapt['precision']:.2f}", f"{adapt['precision'] - inf['precision']:+.2f} vs in-farm", delta_color="inverse")
    st.metric("Recall on the other farm", f"{adapt['recall']:.2f}", f"{adapt['recall'] - inf['recall']:+.2f} vs in-farm", delta_color="off")
    st.metric("ROC-AUC on the other farm", f"{adapt['roc_auc']:.2f}", f"{adapt['roc_auc'] - inf['roc_auc']:+.2f} vs in-farm", delta_color="inverse")
    st.caption("Per-farm normalisation uses the target farm's own early (healthy) data - no labels, no retraining. Without it the transfer collapses.")
st.dataframe(pd.DataFrame(v["fault_kind"]).rename(columns={"kind": "Fault kind", "n": "Failures", "median_percentile": "Median risk percentile before failure"}), hide_index=True, width="stretch")

with st.expander("Days-to-failure (RUL) regression and per-failure warnings"):
    st.dataframe(pd.DataFrame(v["rul"]), hide_index=True, width="stretch")
    st.caption("Days-to-failure beats the constant baseline only modestly. It is shown as a rough guide, not a countdown.")
    ep = pd.DataFrame(v["episodes"]); ep["Warned"] = ep["warned_watch"].map({1.0: "✓ yes", 0.0: "✗ missed"}).fillna("–")
    st.dataframe(ep[["turbine", "message", "t_fail", "Warned"]].rename(columns={"turbine": "Turbine", "message": "Failure", "t_fail": "Failed at"}), hide_index=True, width="stretch")
