"""Page 5 - Validation & Cross-Farm: headline metrics, ROC / PR curves, confusion matrix, cross-farm transfer, cross-validation, protocol."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
ri = meta["run_info"]
ui.page_header("Validation & Cross-Farm", "Validation & Cross-Farm", "How reliable is the model? A chronological hold-out test, cross-validation, bootstrap intervals and a test on a second wind farm.",
               ui.header_chips(meta))
v = api.get("/validation/summary")
g = api.get("/explain/global")
models = pd.DataFrame(g["models"]).set_index("model")
fused = models.loc["Fused risk score"]
ci = pd.DataFrame(v["ci"]).set_index("model")


def ci_of(model, col):
    x = str(ci.loc[model, col]) if model in ci.index else ""
    return "95% CI " + x.split(" ", 1)[1] if " " in x else ""


# ---- setup strip ------------------------------------------------------------------------------------------------------------------------
with st.container(border=True):
    s = st.columns(4)
    s[0].markdown(ui.stat("Active architecture", "Fused risk score", "average of Logistic Regression, Random Forest, Gradient Boosting"), unsafe_allow_html=True)
    s[1].markdown(ui.stat("Evaluation window", f"Hold-out {ri['test_year']}", f"train {ri['train_years'][0]}–{ri['train_years'][-1]} · validate {ri['val_year']}"), unsafe_allow_html=True)
    s[2].markdown(ui.stat("Source farm (trained on)", "Kelmarsh", "6 turbines"), unsafe_allow_html=True)
    s[3].markdown(ui.stat("Test farm (no retraining)", "Penmanshiel", "14 turbines · 10 common sensors"), unsafe_allow_html=True)

# ---- KPI row ----------------------------------------------------------------------------------------------------------------------------
k = st.columns(5)
ui.kpi(k[0], "ROC-AUC", f"{fused['roc_auc']:.3f}", ci_of("Fused risk score", "roc_auc") or "discrimination across thresholds", "show_chart", "blue")
ui.kpi(k[1], "Precision", f"{fused['precision']:.3f}", ci_of("Fused risk score", "precision") or "alerts that were real", "target", "green")
ui.kpi(k[2], "Recall (sensitivity)", f"{fused['recall']:.3f}", ci_of("Fused risk score", "recall") or "pre-failure hours flagged", "radar", "teal")
ui.kpi(k[3], "F1-score", f"{fused['f1']:.3f}", ci_of("Fused risk score", "f1") or "balance of precision and recall", "balance", "amber")
ui.kpi(k[4], "Accuracy", f"{fused['accuracy']:.3f}", "'always normal' scores 0.958", "check_circle", "blue")

# ---- curves + confusion matrix ----------------------------------------------------------------------------------------------------------
c1, c2 = st.columns([1.3, 1])
MODELS = {"Fused risk score": "risk", "Random Forest": "p_random_forest", "Gradient Boosting": "p_gradient_boosting", "Logistic Regression": "p_logistic", "SVM": "p_svm", "ANN": "p_ann", "Naive Bayes": "p_bayes"}
with c1.container(border=True):
    ui.card_head("ROC and Precision-Recall Curves", "Hold-out test year; AUC in brackets")
    curve = st.segmented_control("Curve", ["ROC", "Precision-Recall"], default="ROC", key="val_curve", label_visibility="collapsed") or "ROC"
    sel = st.multiselect("Models", list(MODELS), default=["Fused risk score", "Random Forest", "Gradient Boosting", "Logistic Regression"], max_selections=6, key="val_models", label_visibility="collapsed")
    if sel:
        cv = api.get("/validation/curves", models=",".join(MODELS[x] for x in sel))
        colr = alt.Color("model:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(title=None, orient="bottom", columns=2))
        if curve == "ROC":
            d = pd.concat([pd.DataFrame(dict(fpr=x["roc"]["fpr"], tpr=x["roc"]["tpr"], model=f"{k_} ({x['roc_auc']:.2f})")) for k_, x in cv.items()])
            diag = alt.Chart(pd.DataFrame(dict(x=[0, 1], y=[0, 1]))).mark_line(strokeDash=[4, 4], color=ui.MUTED).encode(x="x:Q", y="y:Q")
            ui.show(alt.Chart(d).mark_line(strokeWidth=2).encode(x=alt.X("fpr:Q", title="false-positive rate"), y=alt.Y("tpr:Q", title="true-positive rate"), color=colr, tooltip=["model", "fpr", "tpr"]) + diag, 330)
            st.caption("Dashed diagonal = a model with no skill.")
        else:
            d = pd.concat([pd.DataFrame(dict(recall=x["pr"]["recall"], precision=x["pr"]["precision"], model=f"{k_} ({x['pr_auc']:.2f})")) for k_, x in cv.items()])
            base = alt.Chart(pd.DataFrame(dict(y=[0.042]))).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(y="y:Q")
            ui.show(alt.Chart(d).mark_line(strokeWidth=2).encode(x=alt.X("recall:Q"), y=alt.Y("precision:Q", scale=alt.Scale(domain=[0, 1])), color=colr, tooltip=["model", "recall", "precision"]) + base, 330)
            st.caption("Dashed line = no-skill level (about 4% of test-year hours are pre-failure).")
with c2.container(border=True):
    ui.card_head("Confusion Matrix", "Move the alert threshold to see the trade-off (hourly replay rows)")
    mname = st.selectbox("Model", list(MODELS), index=0, key="val_cm_model", label_visibility="collapsed")
    base = api.get("/validation/confusion", model=MODELS[mname])
    thr = st.slider("Threshold", 0.01, 0.99, float(min(max(base["default_threshold"], 0.01), 0.99)), 0.01, key=f"val_thr_{mname}")
    cm = api.get("/validation/confusion", model=MODELS[mname], threshold=thr)
    grid = pd.DataFrame([dict(actual="Pre-failure", pred="Alert", n=cm["tp"], what="caught"), dict(actual="Pre-failure", pred="No alert", n=cm["fn"], what="missed"),
                         dict(actual="Healthy", pred="Alert", n=cm["fp"], what="false alarm"), dict(actual="Healthy", pred="No alert", n=cm["tn"], what="correctly quiet")])
    h = alt.Chart(grid).mark_rect(stroke="#ffffff", strokeWidth=3, cornerRadius=6).encode(x=alt.X("pred:N", title="model says", sort=["Alert", "No alert"], axis=alt.Axis(labelAngle=0)),
                                                                                         y=alt.Y("actual:N", title="reality", sort=["Pre-failure", "Healthy"]),
                                                                                         color=alt.Color("n:Q", scale=alt.Scale(range=["#cde2fb", "#0d366b"], type="sqrt"), legend=None), tooltip=["actual", "pred", "what", "n"])
    t = alt.Chart(grid).mark_text(fontSize=17, fontWeight="bold").encode(x=alt.X("pred:N", sort=["Alert", "No alert"]), y=alt.Y("actual:N", sort=["Pre-failure", "Healthy"]), text=alt.Text("n:Q", format=","),
                                                                        color=alt.condition(alt.datum.n > cm["tn"] * 0.05, alt.value("white"), alt.value(ui.INK)))
    ui.show(h + t, 215)
    m = st.columns(4)
    for col, (lab, val) in zip(m, [("Precision", cm["precision"]), ("Recall", cm["recall"]), ("F1", cm["f1"]), ("Specificity", cm["specificity"])]):
        col.markdown(ui.stat(lab, f"{val:.2f}", ""), unsafe_allow_html=True)
    st.caption(cm["note"])

# ---- cross-farm -------------------------------------------------------------------------------------------------------------------------
cf = pd.DataFrame(v["crossfarm"]); gb = cf[cf["model"] == "Gradient Boosting"].copy()
inf = gb[gb["farm"].str.contains("in-farm")].iloc[0]; own = gb[gb["normalisation"].str.contains("per-farm")].iloc[0]; raw = gb[gb["normalisation"].str.contains("no adaptation")].iloc[0]
x1, x2 = st.columns([1.5, 1])
with x1.container(border=True):
    ui.card_head("Cross-Farm Generalization & Domain Transfer", "Gradient Boosting trained on Kelmarsh, tested on Penmanshiel without retraining (10 sensors both farms have)")
    gb["setting"] = ["Kelmarsh 2022 (same farm)" if "in-farm" in f else ("Penmanshiel · scaled with its own early data" if "per-farm" in n else "Penmanshiel · scaled with Kelmarsh statistics") for f, n in zip(gb["farm"], gb["normalisation"])]
    long = gb.melt(id_vars="setting", value_vars=["roc_auc", "pr_auc", "precision", "recall"], var_name="metric", value_name="value")
    long["metric"] = long["metric"].map({"roc_auc": "ROC-AUC", "pr_auc": "PR-AUC", "precision": "Precision", "recall": "Recall"})
    ch = alt.Chart(long).mark_bar(cornerRadiusEnd=3).encode(x=alt.X("metric:N", title=None, axis=alt.Axis(labelAngle=0), sort=["ROC-AUC", "PR-AUC", "Precision", "Recall"]), xOffset="setting:N",
                                                            y=alt.Y("value:Q", scale=alt.Scale(domain=[0, 1]), title=None),
                                                            color=alt.Color("setting:N", scale=alt.Scale(range=ui.SERIES[:3]), legend=alt.Legend(orient="bottom", columns=1, title=None, labelLimit=420)), tooltip=["setting", "metric", alt.Tooltip("value:Q", format=".2f")])
    txt = ch.mark_text(dy=-6, fontSize=10, color=ui.MUTED).encode(text=alt.Text("value:Q", format=".2f"), y="value:Q")
    ui.show(ch + txt, 330)
with x2.container(border=True):
    ui.card_head("Generalization Verdict", "What is lost on the second farm")
    st.markdown(f'<div class="wg-sline"><span>ROC-AUC</span><span><b>{own["roc_auc"]:.2f}</b> <span class="m">{own["roc_auc"] - inf["roc_auc"]:+.2f} vs same farm</span></span></div>'
                f'<div class="wg-sline"><span>Precision</span><span><b>{own["precision"]:.2f}</b> <span class="m">{own["precision"] - inf["precision"]:+.2f} vs same farm</span></span></div>'
                f'<div class="wg-sline"><span>Recall</span><span><b>{own["recall"]:.2f}</b> <span class="m">{own["recall"] - inf["recall"]:+.2f} vs same farm</span></span></div>'
                f'<div class="wg-sline"><span>PR-AUC without farm-specific scaling</span><span><b>{raw["pr_auc"]:.2f}</b> <span class="m">vs {own["pr_auc"]:.2f} with it</span></span></div>', unsafe_allow_html=True)
    st.markdown('<div class="wg-note" style="margin-top:10px">Farm-specific scaling uses only the second farm\'s own early, healthy data (no failure labels, no retraining). Without it the transfer collapses, so a new farm needs a short baseline period before the model is trusted.</div>', unsafe_allow_html=True)

# ---- cross-validation + protocol --------------------------------------------------------------------------------------------------------
y1, y2 = st.columns([1.5, 1])
with y1.container(border=True):
    ui.card_head("Cross-Validation on the Training Years", "5-fold grouped cross-validation, PR-AUC mean ± 1 standard deviation")
    cvd = pd.DataFrame(v["cv"]); cvd["lo"] = cvd["pr_auc_mean"] - cvd["pr_auc_sd"]; cvd["hi"] = cvd["pr_auc_mean"] + cvd["pr_auc_sd"]
    bar = alt.Chart(cvd).mark_bar(color=ui.SERIES[0], cornerRadiusEnd=3, size=18).encode(y=alt.Y("model:N", sort="-x", title=None), x=alt.X("pr_auc_mean:Q", title="PR-AUC", scale=alt.Scale(domain=[0, 1])),
                                                                                       tooltip=["model", alt.Tooltip("pr_auc_mean:Q", format=".3f"), alt.Tooltip("pr_auc_sd:Q", format=".3f")])
    err = alt.Chart(cvd).mark_rule(color=ui.INK, strokeWidth=1.6).encode(y=alt.Y("model:N", sort="-x"), x="lo:Q", x2="hi:Q")
    lab = alt.Chart(cvd).mark_text(align="left", dx=6, fontSize=11, color=ui.MUTED).encode(y=alt.Y("model:N", sort="-x"), x="hi:Q", text=alt.Text("pr_auc_mean:Q", format=".2f"))
    ui.show(bar + err + lab, 210)
    st.caption("Folds are grouped by turbine and two-week block, so neighbouring hours never sit on both sides of a split. Only the mean and spread per model are stored, not each fold.")
with y2.container(border=True):
    ui.card_head("Evaluation Protocol & Integrity", "How the numbers were produced")
    items = [("Chronological split", f"train {ri['train_years'][0]}–{ri['train_years'][-1]}, validation {ri['val_year']}, test {ri['test_year']}: no hour appears in two sets"),
             ("Thresholds from validation only", f"Watch {ri['fused_watch_threshold']:.2f} and High {ri['fused_high_threshold']:.2f} were chosen on {ri['val_year']} and applied unchanged"),
             ("Healthy-only fitting", "normal-behaviour models and the scaler use healthy training hours only"),
             ("Full test year", f"{ri['n_test_rows']:,} running hours and {ri['n_test_episodes']} failures, no sampling of the test set (stopped hours and the day after a failure are excluded)"),
             ("Uncertainty reported", "block-bootstrap 95% intervals by turbine-week")]
    st.markdown("".join(f'<div class="wg-sline" style="align-items:flex-start"><span class="msi" style="color:#0ca30c;font-size:18px">check_circle</span><div style="flex:1"><b style="font-size:.86rem">{ui.e(a)}</b><div class="wg-cs">{ui.e(b)}</div></div></div>' for a, b in items), unsafe_allow_html=True)

# ---- bootstrap + fault kinds ------------------------------------------------------------------------------------------------------------
z1, z2 = st.columns([1.5, 1])
with z1.container(border=True):
    ui.card_head("Bootstrap Confidence Intervals", "Point value with 95% interval, test year")
    cols = ["precision", "recall", "f1", "pr_auc", "roc_auc"]
    rows = "".join(f'<tr><td class="nw"><b>{ui.e(m)}</b></td>' + "".join(f'<td class="nw">{ui.e(r[c])}</td>' for c in cols) + '</tr>' for m, r in ci.iterrows())
    st.markdown('<table class="wg-table"><thead><tr><th>Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>PR-AUC</th><th>ROC-AUC</th></tr></thead>' + f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
    st.caption(f"With only {ri['n_test_episodes']} failures in the test year the intervals are wide: read them, not just the point values.")
with z2.container(border=True):
    ui.card_head("Fault Types Still Detected on Penmanshiel", "Median risk percentile in the 7 days before each failure (1.0 = top rank)")
    fk = pd.DataFrame(v["fault_kind"]).sort_values("median_percentile", ascending=False)
    ui.show(alt.Chart(fk).mark_bar(cornerRadiusEnd=3).encode(y=alt.Y("kind:N", sort=None, title=None), x=alt.X("median_percentile:Q", title="median percentile", scale=alt.Scale(domain=[0, 1])),
                                                              color=alt.condition(alt.datum.median_percentile >= 0.9, alt.value(ui.SERIES[0]), alt.value(ui.SERIES[1])),
                                                              tooltip=["kind", "n", alt.Tooltip("median_percentile:Q", format=".2f")]), 240)
    st.caption("Hydraulic faults score low because Penmanshiel has no hydraulic-pressure sensor.")

with st.expander("Days-to-failure (RUL) regression and per-failure warnings"):
    st.dataframe(pd.DataFrame(v["rul"]), hide_index=True, width="stretch")
    st.caption("Days-to-failure beats the constant baseline only modestly. It is shown as a rough guide, not a countdown.")
    ep = pd.DataFrame(v["episodes"]); ep["Warned"] = ep["warned_watch"].map({1.0: "✓ yes", 0.0: "✗ missed"}).fillna("–"); ep["Turbine"] = ep["turbine"].map(ui.tname)
    st.dataframe(ep[["Turbine", "message", "t_fail", "Warned"]].rename(columns={"message": "Failure", "t_fail": "Failed at"}), hide_index=True, width="stretch")
ui.disclaimer_note(meta)
