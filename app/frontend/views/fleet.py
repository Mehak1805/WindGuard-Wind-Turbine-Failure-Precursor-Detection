"""Page 1 - Fleet Overview: hero summary, risk-band donut, fleet risk trend, power curve, regimes, data quality, turbine table."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
ui.page_header("Fleet Overview", "Fleet Overview", "Real-time health of the Kelmarsh turbines: failure-risk status, operating regimes, data quality and the anomaly index of every turbine.",
               ui.header_chips(meta))
WINDOWS = {"24H": 24, "3D": 72, "7D": 168, "30D": 720}
REGIME_COLORS = ["#86b6ef", "#2a78d6", "#184f95", "#eb6834"]


def render():
    snap = api.get("/fleet/snapshot")
    k, T, rated = snap["kpis"], snap["turbines"], snap["rated_kw"]
    live = [t for t in T if not t["offline"]]
    mw = lambda ts: sum((t["power"] or 0) for t in ts) / 1000
    producing = sum(t["operating"] == "Producing" for t in live)

    # ---- row 1: hero + fleet status ------------------------------------------------------------------------------------------------
    c1, c2 = st.columns([1.45, 1])
    with c1:
        st.markdown(f"""<div class="wg-hero"><div><div class="t">Kelmarsh wind farm</div><div class="s">{k['turbines']} turbines monitored · replay time {snap['sim_time']}</div></div>
<div class="row"><div class="box"><div class="l">Total units</div><div class="v">{k['turbines']}</div><div class="u">turbines</div></div>
<div class="box"><div class="l">Active output</div><div class="v">{mw(live):.1f} MW</div><div class="u">{producing} of {k['turbines']} producing (rated {rated:,.0f} kW each)</div></div>
<div class="box"><div class="l">Fleet mean risk</div><div class="v">{ui.pct(k['fleet_risk_mean'])}</div><div class="u">fused 7-day failure risk</div></div></div></div>""", unsafe_allow_html=True)
    with c2.container(border=True):
        ui.card_head("Fleet Status", "Turbines by fused-risk band right now")
        a, b = st.columns([1, 1.15], vertical_alignment="center")
        parts = [(ui.BAND_LABEL[bd], sum(t["band"] == bd for t in live), ui.BAND_COLOR[bd]) for bd in ui.BAND_ORDER]
        a.altair_chart(ui.donut(parts, k["turbines"], "turbines", 170), width="content")
        rows = ""
        for bd in ui.BAND_ORDER:
            ts = [t for t in live if t["band"] == bd]
            names = ", ".join(ui.tname(t["turbine_id"]) for t in ts) if ts else "none"
            rows += (f'<div class="wg-sline"><div class="wg-legend"><span class="wg-dot" style="background:{ui.BAND_COLOR[bd]}"></span><b>{ui.BAND_LABEL[bd]}</b></div>'
                     f'<div style="text-align:right"><b>{len(ts)}</b> <span class="m">turbine{"s" if len(ts) != 1 else ""} · {mw(ts):.1f} MW</span></div></div>')
        b.markdown(rows, unsafe_allow_html=True)
        st.caption(f"Nominal / Observation / Critical = fused risk below {meta['thresholds']['watch']:.0%} / above {meta['thresholds']['watch']:.0%} (Watch) / above {meta['thresholds']['high']:.0%} (High).")

    # ---- row 2: fleet risk trend + power curve --------------------------------------------------------------------------------------
    r1, r2 = st.columns([1.35, 1])
    with r1.container(border=True):
        ui.card_head("Fleet Risk Trend", "Mean and highest fused failure risk across the turbines")
        win = st.segmented_control("Window", list(WINDOWS), default="24H", key="fleet_win", label_visibility="collapsed") or "24H"
        d = pd.DataFrame(api.get("/fleet/risk_series", hours=WINDOWS[win]))
        if len(d):
            d["ts"] = pd.to_datetime(d["ts"])
            long = d.melt("ts", value_vars=["mean_risk", "max_risk"], var_name="s", value_name="risk")
            long["Series"] = long["s"].map({"mean_risk": "Fleet mean", "max_risk": "Highest turbine"})
            top = max(meta["thresholds"]["watch"] * 1.3, float(d["max_risk"].max()) * 1.08)
            ch = alt.Chart(long).mark_line(strokeWidth=2).encode(
                x=alt.X("ts:T", title=None, axis=ui.tx("%H:%M" if win == "24H" else "%d %b", 6)), y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, top]), axis=alt.Axis(format="%")),
                color=alt.Color("Series:N", scale=alt.Scale(domain=["Fleet mean", "Highest turbine"], range=[ui.SERIES[0], ui.SERIES[1]])),
                tooltip=[alt.Tooltip("ts:T", title="time"), "Series", alt.Tooltip("risk:Q", format=".1%")])
            ui.show(ch + ui.threshold_rules(meta["thresholds"]["watch"], meta["thresholds"]["high"]), 250)
            s = st.columns(3)
            s[0].markdown(ui.stat("Lowest fleet mean", ui.pct(d["mean_risk"].min()), f"in the last {win}"), unsafe_allow_html=True)
            s[1].markdown(ui.stat("Highest single turbine", ui.pct(d["max_risk"].max()), f"in the last {win}"), unsafe_allow_html=True)
            s[2].markdown(ui.stat("Fleet mean", ui.pct(d["mean_risk"].mean()), "average over the window"), unsafe_allow_html=True)
            st.caption("Dashed lines = Watch and High thresholds chosen on the 2021 validation year.")
    with r2.container(border=True):
        pc = api.get("/fleet/power_curve", days=7)
        ui.card_head("Power Output vs. Wind Speed", "Hourly readings of all turbines, last 7 days", ui.pill(f"Capacity factor {ui.pct(pc['capacity_factor'], 0)}", "info") if pc["capacity_factor"] is not None else "")
        p = pd.DataFrame(pc["points"])
        if len(p):
            p["Turbine"] = p["turbine_id"].map(ui.tname)
            sc = alt.Chart(p).mark_circle(size=26, opacity=0.45, color=ui.SERIES[0]).encode(
                x=alt.X("wind:Q", title="wind speed (m/s)"), y=alt.Y("power:Q", title="power (kW)"), tooltip=["Turbine", alt.Tooltip("wind:Q", format=".1f"), alt.Tooltip("power:Q", format=".0f")])
            rule = alt.Chart(pd.DataFrame(dict(y=[rated]))).mark_rule(strokeDash=[5, 4], color=ui.MUTED).encode(y="y:Q")
            ui.show(sc + rule, 340)
            st.caption(f"Dashed line = rated power ({rated:,.0f} kW). Capacity factor = average power ÷ rated power over the same 7 days.")

    # ---- row 3: regimes + data quality -----------------------------------------------------------------------------------------------
    g1, g2 = st.columns([1, 1.25])
    with g1.container(border=True):
        ui.card_head("Operating Regime Distribution", "K-Means clustering of wind speed and power")
        html = ""
        for i, name in enumerate(snap["regimes"]):
            share = snap["regime_share"].get(name, 0); rs = snap["regime_stats"][name]
            html += (f'<div style="margin:12px 0 4px 0"><div style="display:flex;justify-content:space-between;gap:8px"><b style="font-size:.88rem">Regime {i + 1} · {name}</b>'
                     f'<span class="wg-cs">{rs["turbines_now"]} turbine{"s" if rs["turbines_now"] != 1 else ""} now · {share:.0f}% of last 30 d</span></div>'
                     f'{ui.bar(share, 100, REGIME_COLORS[i])}<div class="wg-cs">average wind {rs["wind_mean"] if rs["wind_mean"] is not None else "–"} m/s · average power {rs["power_mean"] if rs["power_mean"] is not None else "–"} kW</div></div>')
        st.markdown(html, unsafe_allow_html=True)
        st.caption("Risk is judged within the regime a turbine is running in, so a hot gearbox at rated power is not flagged just for being busy.")
    with g2.container(border=True):
        ui.card_head("SCADA Data Quality", "Completeness and freshness of the feed (last 7 days)")
        comp = sum(t["completeness"] for t in T) / max(len(T), 1)
        flat = sum(t["flatlined_sensors"] for t in T); age = max(t["age_hours"] for t in T)
        q = st.columns(3)
        q[0].markdown(ui.stat("Completeness", ui.pct(comp), "hours with all 9 channels present"), unsafe_allow_html=True)
        q[1].markdown(ui.stat("Flat-lined sensors", str(flat), "no change in the last 24 h"), unsafe_allow_html=True)
        q[2].markdown(ui.stat("Oldest reading", f"{age:.0f} h", "age of the newest record, worst turbine"), unsafe_allow_html=True)
        lines = ""
        for t in T:
            ok = t["completeness"] >= 0.98 and t["flatlined_sensors"] == 0 and t["age_hours"] <= 2
            lines += (f'<div class="wg-sline"><div><b>{ui.tname(t["turbine_id"])}</b></div><div class="m">complete {t["completeness"] * 100:.1f}% · flat-lined {t["flatlined_sensors"]} · last data {t["age_hours"]:.0f} h ago</div>'
                      f'<div>{ui.pill("OK", "ok", "check_circle") if ok else ui.pill("Check", "warn", "warning")}</div></div>')
        st.markdown(lines, unsafe_allow_html=True)

    # ---- row 4: turbine table --------------------------------------------------------------------------------------------------------
    with st.container(border=True):
        ui.card_head("Turbine Fleet Telemetry & Anomaly Index", "Latest SCADA readout, sensor-deviation (anomaly) score and failure risk. Anomaly score 1.0 = 99th percentile of healthy 2021 behaviour.")
        f1, f2 = st.columns([2, 3])
        text = f1.text_input("Search", placeholder="Search turbine, e.g. KLM-04", label_visibility="collapsed", key="fleet_search")
        flt = f2.segmented_control("Status", ["All", "Nominal", "Observation", "Critical"], default="All", key="fleet_filter", label_visibility="collapsed") or "All"
        rows = sorted(T, key=lambda t: -t["risk"])
        if flt != "All":
            rows = [t for t in rows if ui.BAND_LABEL[t["band"]] == flt]
        if text:
            rows = [t for t in rows if text.lower() in ui.tname(t["turbine_id"]).lower()]
        W = [1.0, 1.2, 1.3, 1.8, 1.3, 2.4, 1.1]
        h = st.columns(W)
        for col, lab in zip(h, ["TURBINE", "REGIME", "HEALTH STATUS", "ANOMALY SCORE", "FAILURE RISK", "LATEST SCADA READOUT", "ACTION"]):
            col.markdown(f'<div class="wg-th">{lab}</div>', unsafe_allow_html=True)
        for t in rows:
            c = st.columns(W, vertical_alignment="center")
            c[0].markdown(f'<div><b>{ui.tname(t["turbine_id"])}</b></div><div class="wg-cs">Kelmarsh</div>', unsafe_allow_html=True)
            c[1].markdown(f'<div style="font-size:.85rem">{t["regime"]}</div>', unsafe_allow_html=True)
            c[2].markdown(ui.badge(t["band"]), unsafe_allow_html=True)
            c[3].markdown(ui.barrow(t["anomaly"], 3.0, ui.BAND_COLOR["High"] if t["anomaly"] >= 1.5 else ui.BRAND, f"{t['anomaly']:.2f}"), unsafe_allow_html=True)
            c[4].markdown(f'<div><b>{ui.pct(t["risk"])}</b> <span class="wg-cs">{ui.BAND_LABEL[t["band"]]}</span></div>', unsafe_allow_html=True)
            gear = "–" if t["gear_oil"] is None else f"{t['gear_oil']:.1f} °C"; hyd = "–" if t["hydraulic"] is None else f"{t['hydraulic']:.0f} bar"
            c[5].markdown(f'<div style="font-size:.85rem">{t["wind"]} m/s · {t["power"]:.0f} kW</div><div class="wg-cs">Gear oil {gear} · Hydraulic {hyd}</div>', unsafe_allow_html=True)
            if c[6].button("Investigate" if t["band"] == "High" else "Inspect", key=f"insp_{t['turbine_id']}", type="primary" if t["band"] == "High" else "secondary", width="stretch"):
                ui.go_turbine(t["turbine_id"])
            st.markdown('<hr class="wg-hr">', unsafe_allow_html=True)
        if not rows:
            st.info("No turbine matches this filter.")
    ui.disclaimer_note(meta)


ui.live_fragment(render)()
