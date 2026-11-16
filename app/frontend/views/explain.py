"""Page 4 - Explainability & Models: why an alert was raised, feature importance, model benchmark, reliability notes."""
import os, re, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
ui.page_header("Explainability & Models", "Explainability & Models", "Understand which sensors influenced a prediction and how the models behind the fused risk score compare on the 2022 test year.",
               ui.header_chips(meta))
g = api.get("/explain/global")
v = api.get("/validation/summary")
models = pd.DataFrame(g["models"])
al = api.get("/alerts", limit=60)


def clean(sensor):
    return re.sub(r" \(.*\)", "", sensor)


def sigma_bars(df, xcol, xtitle, height=230):
    ch = alt.Chart(df).mark_bar(cornerRadiusEnd=3).encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)), x=alt.X(f"{xcol}:Q", title=xtitle),
                                                          color=alt.condition(alt.datum[xcol] > 0, alt.value(ui.SERIES[0]), alt.value(ui.BAND_COLOR["High"])), tooltip=["sensor", alt.Tooltip(f"{xcol}:Q", format=".2f")])
    ui.show(ch, height)


# ---- row 1: inference target + what influenced it ----------------------------------------------------------------------------------------
ex = None
c1, c2 = st.columns([1, 1.5])
with c1.container(border=True):
    ui.card_head("Inference Target", "Choose an alert raised during the replay")
    if not al:
        st.info("No alerts yet. Let the replay run or press **Next alert** in the sidebar.")
    else:
        labels = {a["alert_id"]: f"{ui.tname(a['turbine_id'])} · {pd.Timestamp(a['start']).strftime('%b %d %H:%M')} · {ui.BAND_LABEL[a['band']]} · {a['status']}" for a in al}
        pick = st.selectbox("Alert", list(labels), format_func=labels.get, label_visibility="collapsed", key="explain_alert")
        ex = api.get(f"/explain/alert/{pick}")
        a = next(x for x in al if x["alert_id"] == pick)
        kind = {"Failure confirmed": "crit", "Open": "warn", "False alarm": "muted"}.get(a["status"], "muted")
        g1 = st.columns(2)
        g1[0].markdown(ui.stat("Turbine", ui.tname(ex["turbine_id"]), f"regime: {ex['regime']}"), unsafe_allow_html=True)
        g1[1].markdown(ui.stat("Peak risk", ui.pct(ex["peak_risk"], 0), pd.Timestamp(ex["peak_ts"]).strftime("%b %d %H:%M")), unsafe_allow_html=True)
        g1 = st.columns(2)
        g1[0].markdown(ui.stat("Severity", ui.badge(ex["band"]), f"{a['hours']} h flagged"), unsafe_allow_html=True)
        g1[1].markdown(ui.stat("Outcome", ui.pill(a["status"], kind), f"{a['fault']} · {a['lead_days']:.1f} d ahead" if a["status"] == "Failure confirmed" else "judged at replay time"), unsafe_allow_html=True)
with c2.container(border=True):
    ui.card_head("What influenced this prediction?", "The sensors that moved most from this turbine's normal level for its load, at the alert's peak")
    if ex:
        if ex["drivers"]:
            rows = ""
            for d in ex["drivers"][:3]:
                direction = "above" if d["sigma"] > 0 else "below"
                sig_txt = f"{d['sigma']:+.1f}σ"
                rows += (f'<div class="wg-sline"><div><b>{ui.e(clean(d["sensor"]))}</b><div class="wg-cs">{abs(d["sigma"]):.1f}σ {direction} its normal level for this load</div></div>'
                         f'<div style="min-width:150px">{ui.barrow(abs(d["sigma"]), max(abs(x["sigma"]) for x in ex["drivers"]) or 1, ui.BRAND if d["sigma"] > 0 else ui.BAND_COLOR["High"], sig_txt)}</div></div>')
            st.markdown(rows, unsafe_allow_html=True)
        else:
            st.markdown('<div class="wg-note">No single sensor stands out at the peak: the model reacted to a combination of small shifts.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="wg-note" style="margin-top:10px">Drivers show <b>how far a sensor is from normal</b>, not how much the model weighs it. Peak risk {ui.pct(ex["peak_risk"], 0)} → <b>{ui.BAND_LABEL[ex["band"]]}</b>; '
                    f'the individual models range from {ui.pct(min(ex["model_probs"].values()), 0)} to {ui.pct(max(ex["model_probs"].values()), 0)} (the fused score averages three of them).</div>', unsafe_allow_html=True)

# ---- row 2: feature importance -----------------------------------------------------------------------------------------------------------
with st.container(border=True):
    ui.card_head("Predictive Feature Importance Breakdown", "Local = this alert · Global = whole test year")
    mode = st.segmented_control("Scope", ["Local (this alert)", "Global (all alerts)"], default="Local (this alert)", key="explain_scope", label_visibility="collapsed") or "Local (this alert)"
    if mode.startswith("Local") and ex:
        a1, a2, a3 = st.columns([1.1, 1.1, 1])
        with a1:
            st.markdown("**Top drivers at the peak** (risk model)")
            d = pd.DataFrame(ex["drivers"])
            if len(d):
                d["sensor"] = d["sensor"].map(clean); sigma_bars(d, "sigma", "deviation from normal (σ)")
            else:
                st.caption("No driver above the reporting level.")
        with a2:
            st.markdown("**Condition sensors vs. healthy behaviour** (robust z-score)")
            z = pd.DataFrame(ex["sensor_deviation"]); z["sensor"] = z["sensor"].map(clean); sigma_bars(z, "z", "z-score")
        with a3:
            st.markdown("**Do the models agree?** (probability)")
            mp = pd.DataFrame(dict(model=list(ex["model_probs"]), p=list(ex["model_probs"].values())))
            bars = alt.Chart(mp).mark_bar(color=ui.BRAND, cornerRadiusEnd=3).encode(y=alt.Y("model:N", sort=None, title=None), x=alt.X("p:Q", title=None, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                                                                                     tooltip=["model", alt.Tooltip("p:Q", format=".1%")])
            ui.show(bars, 230)
    else:
        imp = pd.DataFrame(g["importance"]).sort_values("perm_drop_pr_auc", ascending=False); imp["sensor"] = imp["sensor_group"].map(clean)
        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**Permutation importance** (drop in PR-AUC when the sensor is scrambled)")
            ui.show(alt.Chart(imp).mark_bar(color=ui.SERIES[0], cornerRadiusEnd=3).encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)), x=alt.X("perm_drop_pr_auc:Q", title="drop in PR-AUC"),
                                                                                           tooltip=["sensor", alt.Tooltip("perm_drop_pr_auc:Q", format=".3f")]), 360)
        with b2:
            st.markdown("**Random Forest importance** (share of the forest's splits)")
            ui.show(alt.Chart(imp.sort_values("rf_gini_share", ascending=False)).mark_bar(color=ui.SERIES[1], cornerRadiusEnd=3).encode(
                y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)), x=alt.X("rf_gini_share:Q", title="share of importance"), tooltip=["sensor", alt.Tooltip("rf_gini_share:Q", format=".3f")]), 360)
        st.caption("All features made from one sensor are scrambled together. The two rankings differ because correlated sensors share importance in a forest, while permutation measures the effect on actual predictions.")

# ---- row 3: benchmark + how to read ----------------------------------------------------------------------------------------------------
with st.container(border=True):
    ui.card_head("Model Architecture & Benchmark Comparison", "Evaluated on the full 2022 test year; thresholds were chosen on 2021 and applied unchanged")
    fused = models[models["model"] == "Fused risk score"].iloc[0]
    k = st.columns(6)
    for col, (lab, key) in zip(k, [("Accuracy", "accuracy"), ("Precision", "precision"), ("Recall", "recall"), ("F1", "f1"), ("PR-AUC", "pr_auc"), ("ROC-AUC", "roc_auc")]):
        col.markdown(ui.stat(lab, f"{fused[key]:.2f}", "fused score"), unsafe_allow_html=True)
    role = {"Fused risk score": ui.pill("Deployed", "ok"), "Logistic Regression": ui.pill("Fusion component", "info"), "Random Forest": ui.pill("Fusion component", "info"), "Gradient Boosting": ui.pill("Fusion component", "info")}
    rows = ""
    for r in models.sort_values("pr_auc", ascending=False).itertuples():
        rows += (f'<tr><td><b>{ui.e(r.model)}</b><div class="wg-cs">{ui.e(r.family)}</div></td><td>{r.accuracy:.3f}</td><td>{r.precision:.3f}</td><td>{r.recall:.3f}</td><td>{r.f1:.3f}</td>'
                 f'<td>{r.pr_auc:.3f}</td><td>{r.roc_auc:.3f}</td><td>{r.episode_recall:.0%}</td><td>{r.fa_per_turbine_year:.1f}</td><td>{role.get(r.model, ui.pill("Benchmark", "muted"))}</td></tr>')
    st.markdown('<table class="wg-table" style="margin-top:10px"><thead><tr><th>Algorithm</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>PR-AUC</th><th>ROC-AUC</th><th>Failures caught</th><th>False alarms / turbine-yr</th><th>Role</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>', unsafe_allow_html=True)
    st.caption("Accuracy is high for every model because about 96% of hours are normal (always answering 'normal' scores 0.958): use precision, recall and PR-AUC to compare. Failures caught = share of the test-year failures flagged in advance.")
m2, m3 = st.columns([1.6, 1])
with m2:
    with st.container(border=True):
        ui.card_head("How to Read Feature Importance", "A short guide")
        st.markdown('<div style="font-size:.86rem;line-height:1.5"><b>Local vs. global.</b> Local shows what moved in one alert; global shows which sensors matter across the whole year.<br><br>'
                    '<b>Deviation (σ).</b> Each sensor is compared with what the normal-behaviour model expects for the current wind, power and temperature, so a hot gearbox in a gale is not a deviation.<br><br>'
                    '<b>Correlation is not cause.</b> A sensor that moves with the risk is a clue for the engineer to inspect, not a diagnosis.</div>', unsafe_allow_html=True)
with m3:
    with st.container(border=True):
        ui.card_head("Fusion weights", "How the final risk blends its parts")
        fw = pd.DataFrame(g["fusion"])
        st.markdown("".join(f'<div class="wg-sline"><span>{ui.e(x.component)}</span><b>{x.weight:.0%}</b></div>' for x in fw.itertuples()), unsafe_allow_html=True)

# ---- row 4: reliability ----------------------------------------------------------------------------------------------------------------
with st.container(border=True):
    ui.card_head("Reliability Assessment: Model Insights & Operational Limitations", "Figures below come straight from the notebook's test-year evaluation")
    ci = pd.DataFrame(v["ci"]); ci_f = ci[ci["model"] == "Fused risk score"].iloc[0]
    rul = pd.DataFrame(v["rul"]); rul_row = rul[rul["model"] == meta["run_info"]["rul_model"]]
    r2 = float(rul_row["test_r2"].iloc[0]) if len(rul_row) else None
    cf = pd.DataFrame(v["crossfarm"]); own = cf[cf["normalisation"].str.contains("per-farm")]; inf = cf[cf["farm"].str.contains("in-farm")]
    n_ep = meta["run_info"]["n_test_episodes"]
    s1, s2, s3 = st.columns(3)
    s1.markdown(f'<div class="wg-stat"><div class="l">Model strengths</div><div style="font-size:.85rem;line-height:1.55;margin-top:4px">'
                f'• Flags <b>{fused["episode_recall"]:.0%}</b> of the {n_ep} test-year failures in advance, with a median <b>{fused["median_lead_days"]:.1f} days</b> of warning.<br>'
                f'• ROC-AUC <b>{fused["roc_auc"]:.2f}</b>, PR-AUC <b>{fused["pr_auc"]:.2f}</b> against a no-skill level of about 0.04.<br>'
                f'• Thresholds are chosen on 2021 only and applied unchanged to 2022.</div></div>', unsafe_allow_html=True)
    s2.markdown(f'<div class="wg-stat"><div class="l">Operational sensitivities</div><div style="font-size:.85rem;line-height:1.55;margin-top:4px">'
                f'• About <b>{fused["fa_per_turbine_year"]:.1f} false alarms</b> per turbine per year at the chosen threshold.<br>'
                f'• Only {n_ep} failures in the test year, so intervals are wide (PR-AUC {ui.e(ci_f["pr_auc"])}).<br>'
                f'• Days-to-failure estimates are weak (R² {r2:.2f})' + (f'.<br>• On a second farm, precision falls from {inf["precision"].iloc[0]:.2f} to {own["precision"].iloc[0]:.2f} even with farm-specific scaling.' if len(own) and len(inf) else '.') + '</div></div>', unsafe_allow_html=True)
    s3.markdown(f'<div class="wg-stat"><div class="l">Data and demonstration notice</div><div style="font-size:.85rem;line-height:1.55;margin-top:4px">'
                f'• {ui.e(meta["run_info"]["disclaimer"])}<br>• The dashboard replays the notebook\'s stored 2022 scores; it does not score new raw SCADA rows.</div></div>', unsafe_allow_html=True)
