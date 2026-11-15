"""Page 1 - Fleet Overview: turbine status, regimes, data health, fleet risk trend, recent alerts."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Fleet Overview")
meta = api.get("/meta")
hero_img = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "hero.jpg")     # optional: drop a photo here
if os.path.exists(hero_img): st.image(hero_img, width="stretch")
ui.hero("Fleet Overview", "Live failure-risk status of every turbine, the operating regimes they are running in, and the health of the data feed.")


def render():
    snap = api.get("/fleet/snapshot")
    k = snap["kpis"]
    st.caption(f"Replay time **{snap['sim_time']}**  ·  {meta['run_info']['disclaimer']}")

    c = st.columns(5)
    ui.kpi(c[0], "Turbines monitored", k["turbines"], "Kelmarsh-style farm")
    ui.kpi(c[1], "High / Watch now", f"{k['high']} / {k['watch']}", "fused risk bands" + (f" · {k['offline']} offline" if k["offline"] else ""))
    ui.kpi(c[2], "Active alerts", k["active_alerts"], f"{k['alerts_total']} raised so far this year")
    ui.kpi(c[3], "Failures warned", f"{k['failures_warned']} / {k['failures_so_far']}", "failures that happened vs. warned in advance")
    ui.kpi(c[4], "Median warning time", "–" if k["median_lead_days"] is None else f"{k['median_lead_days']:.1f} d", f"{k['false_alarms']} false alarms so far")

    st.markdown("#### Turbine status")
    cols = st.columns(3)
    for i, t in enumerate(snap["turbines"]):
        with cols[i % 3].container(border=True):
            a, b = st.columns([1, 1])
            a.markdown(f"**Turbine {t['turbine_id']}**")
            b.markdown(f"<div style='text-align:right'>{ui.badge(t['band'])}</div>", unsafe_allow_html=True)
            st.markdown("No data for %.0f h - turbine stopped or feed lost" % t["age_hours"] if t["offline"] else f"Risk **{ui.pct(t['risk'])}**  ·  24 h peak {ui.pct(t['risk_24h_max'])}")
            st.caption("last reading " + t["ts"][:16] if t["offline"] else f"{t['operating']} · {t['regime']} · wind {t['wind']} m/s · {t['power']:.0f} kW")
            sp = pd.DataFrame(dict(step=range(len(t["spark"])), risk=t["spark"]))
            ch = alt.Chart(sp).mark_area(line=dict(color=ui.BRAND), color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color="#cde2fb", offset=0), alt.GradientStop(color="#2a78d6", offset=1)],
                                                                                   x1=1, x2=1, y1=1, y2=0)).encode(x=alt.X("step:Q", axis=None), y=alt.Y("risk:Q", axis=None, scale=alt.Scale(domain=[0, max(0.25, max(t["spark"]))])))
            st.altair_chart(ch.properties(height=48).configure_view(strokeWidth=0), width="stretch")

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Fleet risk – daily peak per turbine (last 60 days)")
        tr = api.get("/fleet/trend", days=60)
        d = pd.DataFrame(tr["per_turbine"])
        if len(d):
            d["Turbine"] = "T" + d["turbine_id"].astype(str)
            ch = alt.Chart(d).mark_line(strokeWidth=2).encode(
                x=alt.X("day:T", title=None), y=alt.Y("max_risk:Q", title="peak risk probability", scale=alt.Scale(domain=[0, 1])),
                color=alt.Color("Turbine:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(orient="bottom", columns=6)),
                tooltip=["Turbine", alt.Tooltip("day:T", title="day"), alt.Tooltip("max_risk:Q", format=".2f")])
            rules = alt.Chart(pd.DataFrame(dict(y=[meta["thresholds"]["watch"], meta["thresholds"]["high"]]))).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(y="y:Q")
            ui.show(ch + rules, 280)
    with right:
        st.markdown("#### Operating regimes (last 30 days)")
        rs = pd.DataFrame(dict(regime=snap["regimes"], share=[snap["regime_share"].get(r, 0) for r in snap["regimes"]]))
        ch = alt.Chart(rs).mark_bar(color=ui.BRAND, cornerRadiusEnd=4).encode(
            y=alt.Y("regime:N", sort=snap["regimes"], title=None, axis=alt.Axis(labelLimit=200, labelOverlap=False)), x=alt.X("share:Q", title="% of hours"), tooltip=["regime", alt.Tooltip("share:Q", format=".1f")])
        txt = ch.mark_text(align="left", dx=4, color=ui.INK).encode(text=alt.Text("share:Q", format=".0f"))
        ui.show(ch + txt, 190)
        st.caption("K-Means on wind speed and power: risk is judged within the regime the turbine is running in.")

    l2, r2 = st.columns([2, 3])
    with l2:
        st.markdown("#### Data health")
        h = pd.DataFrame(snap["turbines"])[["turbine_id", "completeness", "flatlined_sensors", "age_hours"]]
        h["status"] = ["✓ OK" if (c_ >= 0.98 and f == 0 and a <= 2) else "▲ Check" for c_, f, a in zip(h["completeness"], h["flatlined_sensors"], h["age_hours"])]
        h["completeness"] = (h["completeness"] * 100).round(1)
        st.dataframe(h.rename(columns={"turbine_id": "Turbine", "completeness": "Complete 7 d (%)", "flatlined_sensors": "Flat-lined sensors", "age_hours": "Last data (h ago)", "status": "Status"}),
                     hide_index=True, width="stretch")
    with r2:
        st.markdown("#### Recent alerts")
        al = api.get("/alerts", limit=8)
        if al:
            df = pd.DataFrame(al)
            df["Turbine"] = df["turbine_id"]; df["Band"] = df["band"].map(lambda b: f"{ui.BAND_ICON[b]} {b}")
            df["Peak risk"] = (df["peak_risk"] * 100).round(0).astype(int).astype(str) + "%"
            df["Started"] = pd.to_datetime(df["start"]).dt.strftime("%b %d %H:%M"); df["Lead (d)"] = pd.to_numeric(df["lead_days"], errors="coerce").round(1)
            st.dataframe(df[["Started", "Turbine", "Band", "Peak risk", "status", "Lead (d)", "fault"]].rename(columns={"status": "Outcome", "fault": "Failure"}), hide_index=True, width="stretch")
        else:
            st.info("No alerts yet in the replayed period.")


ui.live_fragment(render)()
