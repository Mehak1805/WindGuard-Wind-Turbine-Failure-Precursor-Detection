"""Page 2 - Anomaly & Alerts: KPIs, PCA map, severity breakdown, highest-urgency flag, timeline with threshold calibration, alert queue."""
import os, re, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
ui.page_header("Anomaly & Alerts", "Anomaly & Alerts", "Spot unusual turbine behaviour and sensor drift before mechanical degradation occurs: an unsupervised sensor-deviation score next to the supervised risk alerts.",
               ui.header_chips(meta))
WINDOW_DAYS = {"24H": 1, "3D": 3, "7D": 7, "30D": 30}
PRESETS = {"High sensitivity": 1.0, "Balanced": 1.5, "Conservative": 2.5}
if "anom_thr" not in st.session_state:
    st.session_state["anom_thr"] = 1.5

f1, f2, _ = st.columns([1.2, 1.2, 3])
tb_choice = f1.selectbox("Turbine", ["All turbines"] + [ui.tname(t) for t in meta["turbines"]], key="anom_tb")
map_days = f2.select_slider("Map window", options=[7, 14, 30, 45, 90], value=30, format_func=lambda d: f"last {d} days", key="anom_days")
tb = 0 if tb_choice == "All turbines" else int(tb_choice.split("-")[1])


def clean(sensor):
    return re.sub(r" \(.*\)", "", sensor)


def drivers_text(drivers, n=3):
    return "; ".join(f"{clean(d['sensor'])} {d['sigma']:+.1f}σ" for d in drivers[:n]) if drivers else "no single sensor stands out"


def render(tb, map_days):
    snap = api.get("/fleet/snapshot"); T = snap["turbines"]
    active = api.get("/alerts", limit=60, only_active=True)
    al = api.get("/alerts", limit=60)
    live = [t for t in T if not t["offline"]]

    # ---- KPI strip ---------------------------------------------------------------------------------------------------------------
    c = st.columns(4)
    crit = [a for a in active if a["band"] == "High"]
    affected = sorted({a["turbine_id"] for a in active})
    ui.kpi(c[0], "Active anomalies", len(active), f"{len(al)} alerts raised so far in the replay", "monitor_heart", "blue")
    ui.kpi(c[1], "Critical alerts", len(crit), (", ".join(ui.tname(a["turbine_id"]) for a in crit) or "none right now"), "emergency_home", "red")
    ui.kpi(c[2], "Turbines affected", f"{len(affected)} of {len(T)}", ", ".join(ui.tname(x) for x in affected) or "none right now", "wind_power", "amber")
    ui.kpi(c[3], "Avg anomaly score", f"{sum(t['anomaly'] for t in live) / max(len(live), 1):.2f}", "1.0 = 99th percentile of healthy behaviour", "speed", "teal")

    # ---- row: PCA map + severity + urgency -----------------------------------------------------------------------------------------
    m1, m2 = st.columns([1.7, 1])
    with m1.container(border=True):
        sc = api.get("/anomaly/scatter", turbine=tb, days=map_days)
        ui.card_head("Anomaly Detection Map (PCA Feature Space)", f"Principal components of the regime-normalised sensor deviations · PC1 {sc['explained'][0]:.0%} · PC2 {sc['explained'][1]:.0%} of variance")
        pick = st.segmented_control("Regime filter", ["All regimes"] + snap["regimes"] + ["Outliers only"], default="All regimes", key="anom_regime", label_visibility="collapsed") or "All regimes"
        p = pd.DataFrame(sc["points"])
        if len(p):
            if pick == "Outliers only":
                p = p[p["dev_norm"] >= 1.5]
            elif pick != "All regimes":
                p = p[p["regime"] == pick]
        if len(p):
            p["order"] = p["band"].map({"Low": 0, "Watch": 1, "High": 2}); p["Turbine"] = p["turbine_id"].map(ui.tname)
            p["Risk band"] = p["band"].map(ui.BAND_LABEL)
            ch = alt.Chart(p.sort_values("order")).mark_circle(opacity=0.65, stroke="#ffffff", strokeWidth=0.4).encode(
                x=alt.X("pc1:Q", title="PC1"), y=alt.Y("pc2:Q", title="PC2"),
                color=alt.Color("Risk band:N", scale=alt.Scale(domain=[ui.BAND_LABEL[b] for b in ui.BAND_ORDER], range=[ui.BAND_COLOR[b] for b in ui.BAND_ORDER]), legend=alt.Legend(title="Fused risk band")),
                size=alt.Size("band:N", scale=alt.Scale(domain=ui.BAND_ORDER, range=[26, 80, 110]), legend=None),
                tooltip=["Turbine", alt.Tooltip("ts:T", title="time"), "regime", alt.Tooltip("dev_norm:Q", format=".2f", title="anomaly score"), alt.Tooltip("risk:Q", format=".1%", title="fused risk")])
            ui.show(ch, 345)
            st.caption(f"{len(p):,} of {sc['n_window']:,} hourly points drawn. 'Outliers only' = anomaly score ≥ 1.5. Sensors are compared with the turbine's own healthy behaviour in the same regime, so wind and season do not dominate.")
        else:
            st.info("No points for this filter.")
    with m2:
        with st.container(border=True):
            ui.card_head("Severity Breakdown", "Turbines by fused-risk band right now")
            a, b = st.columns([1, 1.1], vertical_alignment="center")
            parts = [(ui.BAND_LABEL[bd], sum(t["band"] == bd for t in live), ui.BAND_COLOR[bd]) for bd in ui.BAND_ORDER]
            a.altair_chart(ui.donut(parts, len(T), "turbines", 150), width="content")
            b.markdown("".join(f'<div class="wg-sline"><div class="wg-legend"><span class="wg-dot" style="background:{ui.BAND_COLOR[bd]}"></span>{ui.BAND_LABEL[bd]}</div><b>{sum(t["band"] == bd for t in live)}</b></div>' for bd in ui.BAND_ORDER),
                       unsafe_allow_html=True)
        with st.container(border=True):
            if active:
                top = sorted(active, key=lambda a: (a["band"] == "High", a["peak_risk"]))[-1]; head, tag = "Highest urgency flag", ui.pill(ui.BAND_LABEL[top["band"]], ui.BAND_KIND[top["band"]])
            elif al:
                top = al[0]; head, tag = "Most recent alert", ui.pill(top["status"], "muted")
            else:
                top = None
            if top:
                ui.card_head(head, "Raised by the fused risk model", tag)
                st.markdown(f'<div style="font-size:1.15rem;font-weight:800">{ui.tname(top["turbine_id"])}</div>'
                            f'<div class="wg-cs">First flagged {pd.Timestamp(top["start"]):%d %b %Y, %H:%M} · {top["hours"]} h flagged · peak risk {ui.pct(top["peak_risk"], 0)}</div>'
                            f'<div style="margin-top:8px;font-size:.86rem"><b>Sensors that moved most:</b> {ui.e(drivers_text(top["top_drivers"]))}</div>', unsafe_allow_html=True)
                if top["status"] == "Failure confirmed":
                    st.markdown(f'<div class="wg-note" style="margin-top:8px">Failure confirmed: {ui.e(top["fault"])}, warned {top["lead_days"]:.1f} days ahead.</div>', unsafe_allow_html=True)
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                if st.button("Investigate telemetry", key="anom_inv", type="primary", width="stretch"):
                    ui.go_turbine(top["turbine_id"])
            else:
                ui.card_head("Highest urgency flag", "")
                st.success("No alerts yet in the replayed period.")

    # ---- timeline + calibration ---------------------------------------------------------------------------------------------------
    with st.container(border=True):
        t_ = tb or max(live, key=lambda t: t["anomaly"])["turbine_id"] if live else (tb or 1)
        ui.card_head("Anomaly Timeline & Dynamic Calibration", f"Sensor-deviation score of {ui.tname(t_)}" + ("" if tb else " (the turbine with the highest score right now; pick one above to change)"))
        win = st.segmented_control("Timeline window", list(WINDOW_DAYS), default="7D", key="anom_win", label_visibility="collapsed") or "7D"
        thr = st.session_state["anom_thr"]
        tl = pd.DataFrame(api.get("/anomaly/timeline", turbine=t_, days=WINDOW_DAYS[win]))
        if len(tl):
            tl["ts"] = pd.to_datetime(tl["ts"])
            xax = ui.tx("%H:%M" if win == "24H" else "%d %b", 6)
            line = alt.Chart(tl).mark_line(color=ui.BRAND, strokeWidth=1.8).encode(x=alt.X("ts:T", title=None, axis=xax), y=alt.Y("dev_norm:Q", title="anomaly score"),
                                                                                 tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("dev_norm:Q", format=".2f", title="anomaly score")])
            rule = alt.Chart(pd.DataFrame(dict(y=[thr]))).mark_rule(color=ui.BAND_COLOR["High"], strokeDash=[5, 4]).encode(y="y:Q")
            hits = alt.Chart(tl[tl["dev_norm"] >= thr]).mark_circle(color=ui.BAND_COLOR["High"], size=36).encode(x="ts:T", y="dev_norm:Q")
            ui.show(line + rule + hits, 220)
            rk = alt.Chart(tl).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=1.5)).encode(x=alt.X("ts:T", title=None, axis=xax), y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                                                                                                                tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("risk:Q", format=".1%")])
            ui.show(rk + ui.threshold_rules(meta["thresholds"]["watch"], meta["thresholds"]["high"]), 130)
        cal = st.container(border=True)
        with cal:
            s1, s2 = st.columns([2.2, 1.6], vertical_alignment="center")
            with s1:
                st.slider("Anomaly sensitivity cut-off (1.0 = 99th percentile of healthy 2021 behaviour)", 0.5, 4.0, step=0.1, key="anom_thr")
                pc = st.columns(len(PRESETS))
                for col, (name, v) in zip(pc, PRESETS.items()):
                    col.button(f"{name} ({v:.1f})", key=f"preset_{name}", width="stretch", type="primary" if abs(st.session_state["anom_thr"] - v) < 0.05 else "secondary",
                               on_click=lambda v=v: st.session_state.update(anom_thr=v))
            with s2:
                q = api.get("/anomaly/threshold", value=st.session_state["anom_thr"])
                st.markdown(f'<div class="wg-note">At this cut-off <b>{q["flagged_pct"]}%</b> of test-year hours are flagged: precision <b>{ui.pct(q["precision"], 0)}</b>, recall <b>{ui.pct(q["recall"], 0)}</b>, '
                            f'and <b>{q["episodes_caught"]} of {q["episodes"]}</b> failures show at least one flag in their 7-day window. '
                            f'Score AUC {q["roc_auc"]:.2f} (Isolation Forest: {q["iforest_roc_auc"]:.2f}).</div>', unsafe_allow_html=True)

    # ---- alert queue --------------------------------------------------------------------------------------------------------------
    with st.container(border=True):
        ui.card_head("Fleet Telemetry Anomaly Queue", "Alerts raised by the fused risk model. An outcome is judged only with information available at the replay time.")
        q1, q2 = st.columns([2, 3])
        search = q1.text_input("Filter", placeholder="Filter by turbine, e.g. KLM-04", label_visibility="collapsed", key="anom_search")
        only = q2.segmented_control("Alerts", ["All", "Active"], default="All", key="anom_only", label_visibility="collapsed") or "All"
        rows = [a for a in (active if only == "Active" else al) if (not tb or a["turbine_id"] == tb) and (not search or search.lower() in ui.tname(a["turbine_id"]).lower())][:14]
        if rows:
            out = ""
            for a in rows:
                kind = {"Failure confirmed": "crit", "Open": "warn", "False alarm": "muted"}.get(a["status"], "muted")
                lead = f' · {a["lead_days"]:.1f} d ahead' if a.get("lead_days") == a.get("lead_days") and a.get("lead_days") is not None else ""
                out += (f'<tr><td class="wg-mono">{pd.Timestamp(a["start"]):%d %b %H:%M}</td><td><b>{ui.tname(a["turbine_id"])}</b></td><td>{ui.badge(a["band"])}</td>'
                        f'<td style="min-width:130px">{ui.barrow(a["peak_risk"], 1.0, ui.BAND_COLOR[a["band"]], ui.pct(a["peak_risk"], 0))}</td><td>{a["hours"]} h</td>'
                        f'<td>{ui.pill(a["status"], kind)}<div class="wg-cs">{ui.e(a["fault"])}{lead}</div></td><td style="font-size:.8rem">{ui.e(drivers_text(a["top_drivers"]))}</td></tr>')
            st.markdown('<table class="wg-table"><thead><tr><th>Time</th><th>Turbine</th><th>Severity</th><th>Peak risk</th><th>Flagged</th><th>Outcome</th><th>Root-cause hypotheses (sensors that moved)</th></tr></thead>'
                        f'<tbody>{out}</tbody></table>', unsafe_allow_html=True)
            st.caption(f"Showing {len(rows)} of {len(active) if only == 'Active' else len(al)} alerts. *Failure confirmed* = a failure followed; *False alarm* = 7 days passed without one.")
        else:
            st.info("No alerts for this selection yet.")
    ui.disclaimer_note(meta)


ui.live_fragment(render, 5)(tb, map_days)
