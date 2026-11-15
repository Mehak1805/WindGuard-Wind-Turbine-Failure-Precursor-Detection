"""Page 3 - Turbine Risk: failure probability gauge, per-window risk, model probabilities, expected time to failure."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Turbine Risk")
meta = api.get("/meta")
ui.hero("Turbine Risk", "How likely is a failure in the next 7 days? The fused probability, how the six models vote, and the estimated time left.")
tb = st.selectbox("Turbine", meta["turbines"], format_func=lambda t: f"Turbine {t}")


def render(tb):
    r = api.get(f"/turbine/{tb}/risk")
    th = r["thresholds"]
    if r["data_age_hours"] and r["data_age_hours"] > 6:
        st.warning(f"No new data for {r['data_age_hours']:.0f} h (turbine stopped or feed lost). The score below is the last one received, at {r['timestamp']}.")
    a, b, c = st.columns([1.1, 1.2, 1.4])
    with a.container(border=True):
        st.markdown("**Failure probability (next 7 days)**")
        st.altair_chart(ui.gauge(r["risk_prob"], th["watch"], th["high"]), width="content")
        st.markdown(f"<div style='text-align:center'>{ui.badge(r['band'])}</div>", unsafe_allow_html=True)
        st.caption(f"Watch ≥ {th['watch']:.0%}  ·  High ≥ {th['high']:.0%}  ·  regime: {r['regime']}  ·  {r['timestamp']}")
    with b.container(border=True):
        st.markdown("**Risk per time window** (highest hourly risk)")
        w = r["window_risk"]
        m = st.columns(3)
        for col, (k, lab) in zip(m, [("24h", "last 24 h"), ("72h", "last 3 days"), ("168h", "last 7 days")]):
            col.metric(lab, ui.pct(w[k], 0))
        if r["days_to_failure_est"] is not None:
            st.metric("Estimated days to failure", f"{r['days_to_failure_est']:.1f} d", f"± {r['days_to_failure_mae']:.1f} d typical error", delta_color="off")
            st.caption("Rough guide only: the days-to-failure model explains little of the variation (R² ≈ 0.2).")
        else:
            st.metric("Estimated days to failure", "–")
            st.caption("Only estimated while the turbine is on Watch / High.")
    with c.container(border=True):
        st.markdown("**How the models vote** (probability)")
        mp = pd.DataFrame(dict(model=["Gradient Boosting", "Random Forest", "Logistic Regression", "Bayesian (GNB)", "SVM", "ANN"],
                               p=[r["model_probs"][k] for k in ["gradient_boosting", "random_forest", "logistic", "bayes", "svm", "ann"]]))
        ch = alt.Chart(mp).mark_bar(color=ui.BRAND, cornerRadiusEnd=4).encode(y=alt.Y("model:N", sort=None, title=None), x=alt.X("p:Q", title=None, scale=alt.Scale(domain=[0, 1])),
                                                                              tooltip=["model", alt.Tooltip("p:Q", format=".3f")])
        ui.show(ch + ch.mark_text(align="left", dx=4, color=ui.INK).encode(text=alt.Text("p:Q", format=".0%")), 210)

    d, e = st.columns([3, 2])
    with d.container(border=True):
        st.markdown("**Risk over the last 7 days**")
        sp = pd.DataFrame(r["sparkline_7d"])
        line = alt.Chart(sp).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=2)).encode(
            x=alt.X("ts:T", title=None), y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, 1])), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("risk:Q", format=".2f"), "band"])
        rules = alt.Chart(pd.DataFrame(dict(y=[th["watch"], th["high"]], lab=["Watch", "High"]))).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(y="y:Q")
        ui.show(line + rules, 230)
    with e.container(border=True):
        st.markdown("**Top sensor drivers right now**")
        if r["top_drivers"]:
            dr = pd.DataFrame(r["top_drivers"])
            ch = alt.Chart(dr).mark_bar().encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=220)), x=alt.X("sigma:Q", title="deviation (σ)"),
                                                 color=alt.condition(alt.datum.sigma > 0, alt.value("#2a78d6"), alt.value("#d03b3b")), tooltip=["sensor", "sigma"])
            ui.show(ch, 200)
            st.caption("Blue: above the turbine's normal level for this load · red: below.")
        else:
            st.success("No sensor stands out – the turbine behaves normally for its load.")
    with st.expander("What the common predict() function returned (the API response behind this page)"):
        st.json(r)


ui.live_fragment(render)(tb)
