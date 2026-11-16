"""Page 3 - Turbine Risk: failure-probability dial, fleet side cards, risk over time, model diagnostics, ranked fleet index."""
import os, re, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
ui.page_header("Turbine Risk", "Turbine Risk", "How likely is a failure in the next 7 days? The fused probability, how each model votes, how the risk has moved, and the turbines ranked by risk.",
               ui.header_chips(meta))
WINDOWS = {"24H": 24, "3D": 72, "7D": 168, "14D": 336}
f1, f2, _ = st.columns([1.2, 1.2, 3])
tb = f1.selectbox("Turbine asset", meta["turbines"], format_func=ui.tname, key="turbine_sel")
win = f2.segmented_control("Risk chart window", list(WINDOWS), default="7D", key="risk_win") or "7D"


def clean(sensor):
    return re.sub(r" \(.*\)", "", sensor)


def render(tb, win):
    r = api.get(f"/turbine/{tb}/risk"); snap = api.get("/fleet/snapshot"); gl = api.get("/explain/global")
    T = snap["turbines"]; th = r["thresholds"]; rated = snap["rated_kw"]
    sd = api.get(f"/turbine/{tb}/series", hours=WINDOWS[win]); s = pd.DataFrame(sd["series"]); fails = pd.DataFrame(sd["failures"])
    last = s.iloc[-1] if len(s) else None
    band = r["band"]
    if r["data_age_hours"] and r["data_age_hours"] > 6:
        st.warning(f"No new data for {r['data_age_hours']:.0f} h (turbine stopped or feed lost). The score below is the last one received, at {r['timestamp']}.")

    # ---- row 1: asset + dial | fleet side cards ----------------------------------------------------------------------------------
    c1, c2 = st.columns([1.75, 1])
    with c1.container(border=True):
        a, b = st.columns([1.1, 1], vertical_alignment="center")
        with a:
            ui.card_head(f"{ui.tname(tb)}", "Kelmarsh wind farm", ui.badge(band))
            g = st.columns(2)
            g[0].markdown(ui.stat("Rated capacity", f"{rated / 1000:.2f} MW", "per turbine"), unsafe_allow_html=True)
            g[1].markdown(ui.stat("Current output", f"{last['Power (kW)']:.0f} kW" if last is not None else "–", f"wind {last['Wind speed (m/s)']:.1f} m/s" if last is not None else ""), unsafe_allow_html=True)
            g = st.columns(2)
            g[0].markdown(ui.stat("Operating regime", r["regime"], "K-Means on wind & power"), unsafe_allow_html=True)
            g[1].markdown(ui.stat("Last reading", r["timestamp"][5:16], f"{r['data_age_hours']:.0f} h ago" if r["data_age_hours"] is not None else ""), unsafe_allow_html=True)
        with b:
            st.markdown('<div style="text-align:center;font-weight:700;color:#0f2a3d">Failure probability (next 7 days)</div>', unsafe_allow_html=True)
            st.altair_chart(ui.dial(r["risk_prob"], ui.BAND_COLOR[band], ui.BAND_LABEL[band].upper(), 230), width="content")
            est = f"Estimated days to failure: {r['days_to_failure_est']:.1f} d (± {r['days_to_failure_mae']:.1f})" if r["days_to_failure_est"] is not None else "Days to failure: only estimated while on Watch / High"
            st.caption(f"Watch ≥ {th['watch']:.0%} · High ≥ {th['high']:.0%}. {est}")
    with c2:
        high = [t for t in T if t["band"] == "High"]
        top = max(T, key=lambda t: t["risk"])
        ui.kpi(st, "High-risk turbines", f"{len(high)} of {len(T)}", ", ".join(ui.tname(t["turbine_id"]) for t in high) or "none right now", "emergency_home", "red")
        ui.kpi(st, "Average fleet risk", ui.pct(sum(t["risk"] for t in T) / len(T)), f"highest: {ui.tname(top['turbine_id'])} at {ui.pct(top['risk'])}", "monitoring", "amber")
        ui.kpi(st, "Monitored assets", f"{sum(not t['offline'] for t in T)} / {len(T)}", "turbines with a live SCADA feed", "sensors", "green")

    # ---- row 2: risk over time + drivers | model diagnostics ---------------------------------------------------------------------------
    d1, d2 = st.columns([1.75, 1])
    with d1:
        with st.container(border=True):
            ui.card_head("Risk Probability Over Time", f"Fused failure risk of {ui.tname(tb)} over the last {win}; red lines = failures that already happened")
            if len(s):
                s["ts"] = pd.to_datetime(s["ts"])
                xax = ui.tx("%H:%M" if win == "24H" else "%d %b", 6)
                area = alt.Chart(s).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=2)).encode(
                    x=alt.X("ts:T", title=None, axis=xax, scale=alt.Scale(domain=[s["ts"].min(), s["ts"].max()])), y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                    tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("risk:Q", format=".1%"), alt.Tooltip("band:N")])
                ch = area + ui.threshold_rules(th["watch"], th["high"])
                if len(fails):
                    ch = ch + alt.Chart(fails.assign(t_fail=pd.to_datetime(fails["t_fail"]))).mark_rule(color=ui.BAND_COLOR["High"], strokeWidth=2).encode(x="t_fail:T", tooltip=["message", "t_fail"])
                ui.show(ch, 270)
                q = st.columns(4)
                q[0].markdown(ui.stat("Right now", ui.pct(r["risk_prob"]), ui.BAND_LABEL[band]), unsafe_allow_html=True)
                q[1].markdown(ui.stat("Peak, last 24 h", ui.pct(r["window_risk"]["24h"]), "highest hourly risk"), unsafe_allow_html=True)
                q[2].markdown(ui.stat("Peak, last 3 days", ui.pct(r["window_risk"]["72h"]), "highest hourly risk"), unsafe_allow_html=True)
                q[3].markdown(ui.stat("Peak, last 7 days", ui.pct(r["window_risk"]["168h"]), "highest hourly risk"), unsafe_allow_html=True)
        with st.container(border=True):
            ui.card_head("Top sensor drivers right now", "How far each sensor sits from this turbine's normal level for its current load (σ)")
            if r["top_drivers"]:
                dr = pd.DataFrame(r["top_drivers"]); dr["sensor"] = dr["sensor"].map(clean)
                ch = alt.Chart(dr).mark_bar(cornerRadiusEnd=3).encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=240)), x=alt.X("sigma:Q", title="deviation (σ)"),
                                                                      color=alt.condition(alt.datum.sigma > 0, alt.value(ui.SERIES[0]), alt.value(ui.BAND_COLOR["High"])), tooltip=["sensor", "sigma"])
                ui.show(ch, 150)
                st.caption("Blue: above the normal level for this load · red: below.")
            else:
                st.success("No sensor stands out: the turbine behaves normally for its load.")
    with d2.container(border=True):
        ui.card_head("Model Diagnostics", "Pick a model to see its probability now and its 2022 test results")
        mp = r["model_probs"]
        now = {"Fused risk score": r["risk_prob"], "Random Forest": mp["random_forest"], "Gradient Boosting": mp["gradient_boosting"], "Logistic Regression": mp["logistic"],
               "Naive Bayes": mp["bayes"], "SVM (linear)": mp["svm"], "ANN (64-32)": mp["ann"], "Isolation Forest": None}
        mt = pd.DataFrame(gl["models"]).set_index("model")
        sel = st.radio("Model", list(now), key="risk_model", label_visibility="collapsed", horizontal=False)
        m = mt.loc[sel]
        st.markdown(f'<div class="wg-sline"><span>Probability now</span><b>{ui.pct(now[sel]) if now[sel] is not None else "not a probability (unsupervised score)"}</b></div>', unsafe_allow_html=True)
        g = st.columns(3)
        for col, (lab, key) in zip(g * 2, [("Accuracy", "accuracy"), ("Precision", "precision"), ("Recall", "recall"), ("F1", "f1"), ("PR-AUC", "pr_auc"), ("ROC-AUC", "roc_auc")]):
            col.markdown(ui.stat(lab, f"{m[key]:.2f}", ""), unsafe_allow_html=True)
        imp = pd.DataFrame(gl["importance"]).sort_values("perm_drop_pr_auc", ascending=False).head(3)
        st.markdown('<div class="wg-cs" style="margin-top:8px"><b>Most important sensors (all models)</b></div>', unsafe_allow_html=True)
        st.markdown("".join(f'<div class="wg-sline"><span style="font-size:.82rem">{ui.e(clean(x.sensor_group))}</span><div style="min-width:130px">{ui.barrow(x.perm_drop_pr_auc, float(imp["perm_drop_pr_auc"].max()), ui.BRAND, f"{x.perm_drop_pr_auc:.2f}")}</div></div>' for x in imp.itertuples()), unsafe_allow_html=True)
        st.caption("Fused = plain average of Logistic Regression, Random Forest and Gradient Boosting. Bars: drop in PR-AUC when the sensor is scrambled.")

    # ---- ranked table -----------------------------------------------------------------------------------------------------------------
    with st.container(border=True):
        ui.card_head("Ranked Turbine Risk Fleet Index", "Every turbine ranked by its current 7-day failure probability")
        W = [1.1, 1.3, 2.6, 1.4, 1.4, 1.2]
        h = st.columns(W)
        for col, lab in zip(h, ["TURBINE", "WIND FARM", "PREDICTED RISK PROBABILITY", "RISK CLASS", "PREDICTION HORIZON", "ACTION"]):
            col.markdown(f'<div class="wg-th">{lab}</div>', unsafe_allow_html=True)
        for t in sorted(T, key=lambda t: -t["risk"]):
            c = st.columns(W, vertical_alignment="center")
            sel = " " + ui.pill("SELECTED", "dark") if t["turbine_id"] == tb else ""
            c[0].markdown(f'<div><b>{ui.tname(t["turbine_id"])}</b>{sel}</div>', unsafe_allow_html=True)
            c[1].markdown('<div style="font-size:.85rem">Kelmarsh wind farm</div>', unsafe_allow_html=True)
            c[2].markdown(ui.barrow(t["risk"], 1.0, ui.BAND_COLOR[t["band"]], ui.pct(t["risk"])), unsafe_allow_html=True)
            c[3].markdown(ui.badge(t["band"]), unsafe_allow_html=True)
            c[4].markdown('<div style="font-size:.85rem">next 7 days</div>', unsafe_allow_html=True)
            if c[5].button("View details", key=f"rk_{t['turbine_id']}", width="stretch"):
                ui.go_turbine(t["turbine_id"])
            st.markdown('<hr class="wg-hr">', unsafe_allow_html=True)
    ui.disclaimer_note(meta)
    with st.expander("What the common predict() function returned (the API response behind this page)"):
        st.json(r)


ui.live_fragment(render)(tb, win)
