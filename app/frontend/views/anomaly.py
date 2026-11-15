"""Page 2 - Anomaly & Alerts: PCA scatter, anomaly timeline, threshold slider, alert list."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Anomaly & Alerts")
meta = api.get("/meta")
ui.hero("Anomaly & Alerts", "Unsupervised sensor-deviation score (PCA) next to the supervised risk alerts. Move the threshold and see what it would have caught.")

c1, c2, c3 = st.columns([1, 1, 2])
tb_choice = c1.selectbox("Turbine", ["All"] + [f"Turbine {t}" for t in meta["turbines"]])
days = c2.select_slider("Window", options=[7, 14, 30, 45, 90], value=30, format_func=lambda d: f"last {d} days")
thr = c3.slider("Anomaly threshold (1.0 = 99th percentile of healthy 2021 behaviour)", 0.5, 4.0, 1.5, 0.1)
tb = 0 if tb_choice == "All" else int(tb_choice.split()[1])

# ---- the threshold slider talks to the backend, which re-scores the whole test year --------------------------------------------------
q = api.get("/anomaly/threshold", value=thr)
c = st.columns(6)
ui.kpi(c[0], "Hours flagged", f"{q['flagged_pct']}%", "of all test-year hours")
ui.kpi(c[1], "Precision", ui.pct(q["precision"], 0), "flags that were pre-failure hours")
ui.kpi(c[2], "Recall", ui.pct(q["recall"], 0), "pre-failure hours flagged")
ui.kpi(c[3], "Failures caught", f"{q['episodes_caught']} / {q['episodes']}", "at least one flag in the window")
ui.kpi(c[4], "Deviation score AUC", f"{q['roc_auc']:.2f}", f"Isolation Forest: {q['iforest_roc_auc']:.2f}")
ui.kpi(c[5], "Base rate", ui.pct(q["base_rate"]), "pre-failure hours overall")
st.caption("The unsupervised score is deliberately modest: it sees one sensor snapshot, while the supervised risk model sees 74 trend features. Use it as the early-warning second opinion.")


def render(tb, days, thr):
    left, right = st.columns([1, 1])
    with left:
        sc = api.get("/anomaly/scatter", turbine=tb, days=days)
        st.markdown(f"#### PCA of sensor deviations  <small>(PC1 {sc['explained'][0]:.0%} · PC2 {sc['explained'][1]:.0%} of variance)</small>", unsafe_allow_html=True)
        p = pd.DataFrame(sc["points"])
        if len(p):
            p["order"] = p["band"].map({"Low": 0, "Watch": 1, "High": 2})
            ch = alt.Chart(p.sort_values("order")).mark_circle(opacity=0.6, stroke="#ffffff", strokeWidth=0.4).encode(
                x=alt.X("pc1:Q", title="PC1"), y=alt.Y("pc2:Q", title="PC2"),
                color=alt.Color("band:N", scale=ui.band_scale(), sort=ui.BAND_ORDER, legend=alt.Legend(title="Fused risk band")),
                size=alt.Size("band:N", scale=alt.Scale(domain=ui.BAND_ORDER, range=[25, 70, 90]), legend=None),
                tooltip=[alt.Tooltip("ts:T", title="time"), "turbine_id", "regime", alt.Tooltip("dev_norm:Q", format=".2f", title="deviation score"), alt.Tooltip("risk:Q", format=".2f")])
            ui.show(ch, 330)
            st.caption(f"{sc['n_window']:,} hourly points in the window ({len(p):,} drawn). Sensors are first compared with the turbine's own healthy behaviour in the same regime, so wind and season do not dominate.")
    with right:
        st.markdown("#### Anomaly timeline")
        t_ = tb or 1
        tl = pd.DataFrame(api.get("/anomaly/timeline", turbine=t_, days=days))
        st.caption(f"Turbine {t_}" + ("  (choose a turbine above to change)" if tb == 0 else ""))
        if len(tl):
            line = alt.Chart(tl).mark_line(color=ui.BRAND, strokeWidth=1.5).encode(x=alt.X("ts:T", title=None), y=alt.Y("dev_norm:Q", title="deviation score"))
            rule = alt.Chart(pd.DataFrame(dict(y=[thr]))).mark_rule(color=BAND_RED, strokeDash=[5, 4]).encode(y="y:Q")
            hits = alt.Chart(tl[tl["dev_norm"] >= thr]).mark_circle(color=BAND_RED, size=34).encode(x="ts:T", y="dev_norm:Q")
            ui.show(line + rule + hits, 165)
            rk = alt.Chart(tl).mark_area(color="#86b6ef", line=dict(color=ui.BRAND_DARK)).encode(x=alt.X("ts:T", title=None), y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, 1])))
            rules = alt.Chart(pd.DataFrame(dict(y=[meta["thresholds"]["watch"], meta["thresholds"]["high"]]))).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(y="y:Q")
            ui.show(rk + rules, 150)
    st.markdown("#### Alert list")
    only = st.toggle("Only active alerts", value=False, key="only_active")
    al = api.get("/alerts", limit=60, only_active=only)
    if tb: al = [a for a in al if a["turbine_id"] == tb]
    if al:
        df = pd.DataFrame(al)
        df["Band"] = df["band"].map(lambda b: f"{ui.BAND_ICON[b]} {b}")
        out = pd.DataFrame(dict(Start=pd.to_datetime(df["start"]), Turbine=df["turbine_id"], Band=df["Band"], Hours=df["hours"], Peak=(df["peak_risk"] * 100).round(0),
                                Outcome=df["status"], Lead_days=pd.to_numeric(df["lead_days"], errors="coerce").round(1), Failure=df["fault"]))
        st.dataframe(out, hide_index=True, width="stretch", column_config={"Peak": st.column_config.ProgressColumn("Peak risk %", min_value=0, max_value=100, format="%d"),
                                                                           "Start": st.column_config.DatetimeColumn(format="MMM DD, HH:mm")})
        st.caption("Outcome is judged only with information available at the replay time: an alert becomes *Failure confirmed* when the failure has happened, *False alarm* once 7 days passed without one.")
    else:
        st.info("No alerts for this selection yet.")


BAND_RED = ui.BAND_COLOR["High"]
ui.live_fragment(render, 5)(tb, days, thr)
