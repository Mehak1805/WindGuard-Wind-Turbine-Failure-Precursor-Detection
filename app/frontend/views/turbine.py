"""Page 6 - Turbine Details: asset header and diagnostics, subsystem cards, telemetry history, sensor deviation, alert and failure log."""
import os, re, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

meta = api.get("/meta")
cur = st.session_state.get("turbine_sel", meta["turbines"][0])          # the header is drawn first, so read the current choice from the session
ui.page_header("Turbine Details", f"{ui.tname(cur)} · Diagnostics & Telemetry", "Everything about one turbine: risk, temperatures, pressures, operating regime and its alert and failure history.", ui.header_chips(meta))
f1, f2, _ = st.columns([1.2, 1.6, 2.6])
tb = f1.selectbox("Turbine", meta["turbines"], format_func=ui.tname, key="turbine_sel")
hours = f2.select_slider("History window", options=[24, 72, 168, 336, 720], value=168, format_func=lambda h: f"last {h // 24} day{'s' if h > 24 else ''}", key="tb_hours")

TEMPS = ["Gear oil temperature (°C)", "Front bearing temperature (°C)", "Generator bearing front temperature (°C)", "Stator temperature 1 (°C)"]
PRESS = ["Gear oil inlet pressure (bar)", "Hydraulic oil pressure (bar)"]


def clean(sensor):
    return re.sub(r" \(.*\)", "", sensor)


def drivers_text(drivers, n=3):
    return "; ".join(f"{clean(d['sensor'])} {d['sigma']:+.1f}σ" for d in drivers[:n]) if drivers else "no single sensor stands out"


def render(tb, hours):
    d = api.get(f"/turbine/{tb}/series", hours=hours); r = api.get(f"/turbine/{tb}/risk"); snap = api.get("/fleet/snapshot")
    s = pd.DataFrame(d["series"]); f = pd.DataFrame(d["failures"]); rated = snap["rated_kw"]
    if s.empty:
        st.info("No data yet for this window."); return
    s["ts"] = pd.to_datetime(s["ts"]); last = s.iloc[-1]; band = r["band"]; z = d["latest_z"]

    # ---- header card + diagnostics ------------------------------------------------------------------------------------------------
    h1, h2 = st.columns([1.5, 1])
    with h1.container(border=True):
        ui.card_head(f"{ui.tname(tb)}", "Kelmarsh wind farm · rated 2.05 MW", ui.badge(band))
        a = st.columns(4)
        a[0].markdown(ui.stat("Operating regime", last["regime"], "K-Means on wind & power"), unsafe_allow_html=True)
        a[1].markdown(ui.stat("Current output", f"{last['Power (kW)']:.0f} kW", f"{max(last['Power (kW)'], 0) / rated:.0%} of rated"), unsafe_allow_html=True)
        a[2].markdown(ui.stat("Wind speed", f"{last['Wind speed (m/s)']:.1f} m/s", f"ambient {last['Nacelle ambient temperature (°C)']:.1f} °C"), unsafe_allow_html=True)
        a[3].markdown(ui.stat("Last reading", r["timestamp"][5:16], f"{r['data_age_hours']:.0f} h ago" if r["data_age_hours"] is not None else ""), unsafe_allow_html=True)
        if band != "Low":
            st.markdown(f'<div class="wg-note" style="margin-top:10px"><b>{ui.BAND_LABEL[band]}.</b> Sensors that moved most: {ui.e(drivers_text(r["top_drivers"]))}.</div>', unsafe_allow_html=True)
    with h2.container(border=True):
        ui.card_head("Asset Diagnostics & Probability", "From the common predict() function")
        est = f"{r['days_to_failure_est']:.1f} d (± {r['days_to_failure_mae']:.1f})" if r["days_to_failure_est"] is not None else "not flagged"
        st.markdown(f'<div class="wg-sline"><span>Failure probability (7 days)</span><b>{ui.pct(r["risk_prob"])}</b></div>'
                    f'<div class="wg-sline"><span>Anomaly score (1.0 = 99th pct healthy)</span><b>{r["anomaly_score"]:.2f}</b></div>'
                    f'<div class="wg-sline"><span>Peak risk, last 24 h / 7 days</span><b>{ui.pct(r["risk_24h_max"], 0)} / {ui.pct(r["risk_7d_max"], 0)}</b></div>'
                    f'<div class="wg-sline"><span>Estimated days to failure</span><b>{est}</b></div>', unsafe_allow_html=True)

    # ---- four subsystem cards -----------------------------------------------------------------------------------------------------
    q1, q2, q3, q4 = st.columns(4)
    with q1.container(border=True):
        ui.card_head("Electrical System", "Active power")
        cap = max(last["Power (kW)"], 0) / rated
        st.altair_chart(ui.donut([("output", cap, ui.SERIES[0]), ("spare", max(1 - cap, 0), "#e8edf4")], f"{last['Power (kW)']:.0f}", "kW", 150), width="content")
        st.caption(f"{cap:.0%} of rated power · average over the window {s['Power (kW)'].clip(lower=0).mean():.0f} kW")
    with q2.container(border=True):
        ui.card_head("Wind & Operating Regime", "Conditions the turbine is running in")
        st.markdown(f'<div style="font-size:1.9rem;font-weight:800;margin-top:6px">{last["Wind speed (m/s)"]:.1f} <span style="font-size:1rem;color:#5b6b80">m/s</span></div>'
                    f'<div class="wg-cs">wind speed (hourly mean)</div>'
                    f'<div class="wg-sline" style="margin-top:10px"><span>Regime</span><b>{ui.e(last["regime"])}</b></div>'
                    f'<div class="wg-sline"><span>Ambient temperature</span><b>{last["Nacelle ambient temperature (°C)"]:.1f} °C</b></div>'
                    f'<div class="wg-sline"><span>Window average wind</span><b>{s["Wind speed (m/s)"].mean():.1f} m/s</b></div>', unsafe_allow_html=True)
    with q3.container(border=True):
        ui.card_head("Thermal Health", "Latest temperature and deviation from normal")
        rows = ""
        for sname in TEMPS:
            zz = z.get(sname); hot = zz is not None and abs(zz) >= 2
            rows += (f'<div class="wg-sline"><span style="font-size:.82rem">{ui.e(clean(sname))}</span><span><b>{last[sname]:.1f} °C</b> '
                     f'{ui.pill(f"{zz:+.1f}σ", "warn" if hot else "muted") if zz is not None else ""}</span></div>')
        st.markdown(rows, unsafe_allow_html=True)
        st.caption("σ = robust z-score against this turbine's healthy behaviour in the same regime.")
    with q4.container(border=True):
        ui.card_head("Predictive Risk", "Fused failure risk, last 72 h")
        st.markdown(f'<div style="font-size:1.9rem;font-weight:800;margin-top:2px">{ui.pct(r["risk_prob"])} <span style="font-size:.9rem">{ui.badge(band)}</span></div><div class="wg-cs">horizon: next 7 days</div>', unsafe_allow_html=True)
        sp = pd.DataFrame(r["sparkline_7d"]); sp["ts"] = pd.to_datetime(sp["ts"])
        if len(sp):
            ui.show(alt.Chart(sp.tail(24)).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=2)).encode(x=alt.X("ts:T", axis=None), y=alt.Y("risk:Q", axis=None, scale=alt.Scale(domain=[0, 1]))), 90)

    # ---- telemetry history with tabs -------------------------------------------------------------------------------------------------
    with st.container(border=True):
        ui.card_head("SCADA Multi-Sensor Telemetry History", f"Hourly means over the last {hours // 24} day{'s' if hours > 24 else ''}; red lines = failures that already happened")
        tab = st.segmented_control("Signal group", ["Temperatures", "Pressures", "Power & wind", "Fused risk", "Anomaly score"], default="Temperatures", key="tb_tab", label_visibility="collapsed") or "Temperatures"
        x = alt.X("ts:T", title=None, scale=alt.Scale(domain=[s["ts"].min(), s["ts"].max()]), axis=ui.tx("%H:%M" if hours <= 24 else "%d %b", 6))

        def marks(ch):
            if len(f):
                return ch + alt.Chart(f.assign(t_fail=pd.to_datetime(f["t_fail"]))).mark_rule(color=ui.BAND_COLOR["High"], strokeWidth=2).encode(x="t_fail:T", tooltip=["message", "t_fail"])
            return ch

        def lines(cols, title):
            long = s.melt(id_vars="ts", value_vars=cols, var_name="sensor", value_name="v"); long["sensor"] = long["sensor"].map(clean)
            ch = alt.Chart(long).mark_line(strokeWidth=1.8).encode(x=x, y=alt.Y("v:Q", title=title, scale=alt.Scale(zero=False)),
                                                                   color=alt.Color("sensor:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(orient="bottom", title=None, columns=3, labelLimit=320)),
                                                                   tooltip=["sensor", alt.Tooltip("ts:T"), alt.Tooltip("v:Q", format=".1f")])
            ui.show(marks(ch), 300)

        if tab == "Temperatures":
            lines(TEMPS + ["Nacelle ambient temperature (°C)"], "°C")
        elif tab == "Pressures":
            lines(PRESS, "bar")
        elif tab == "Power & wind":
            pw = alt.Chart(s).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=1.6)).encode(x=x, y=alt.Y("Power (kW):Q", title="power (kW)"), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("Power (kW):Q", format=".0f"), "regime"])
            wd = alt.Chart(s).mark_line(color=ui.SERIES[1], strokeWidth=1.6).encode(x=x, y=alt.Y("Wind speed (m/s):Q", title="wind speed (m/s)"), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("Wind speed (m/s):Q", format=".1f")])
            ui.show(marks(pw), 180); ui.show(wd, 120)
        elif tab == "Fused risk":
            ar = alt.Chart(s).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=2)).encode(x=x, y=alt.Y("risk:Q", title="fused risk", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%")),
                                                                                                            tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("risk:Q", format=".1%"), "band"])
            ui.show(marks(ar + ui.threshold_rules(meta["thresholds"]["watch"], meta["thresholds"]["high"])), 300)
        else:
            ln = alt.Chart(s).mark_line(color=ui.BRAND, strokeWidth=1.8).encode(x=x, y=alt.Y("dev_norm:Q", title="anomaly score (1.0 = 99th pct healthy)"), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("dev_norm:Q", format=".2f")])
            ui.show(marks(ln), 300)

    # ---- deviation + regime ---------------------------------------------------------------------------------------------------------
    w1, w2 = st.columns([1.3, 1])
    with w1.container(border=True):
        ui.card_head("Latest Condition-Sensor Deviation", "Against this turbine's healthy behaviour in the same regime (robust z-score)")
        zd = pd.DataFrame(dict(sensor=[clean(k) for k in z], z=list(z.values())))
        ui.show(alt.Chart(zd).mark_bar(cornerRadiusEnd=3).encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=260)), x=alt.X("z:Q", title="robust z-score"),
                                                                  color=alt.condition(alt.datum.z > 0, alt.value(ui.SERIES[0]), alt.value(ui.BAND_COLOR["High"])), tooltip=["sensor", alt.Tooltip("z:Q", format=".2f")]), 250)
    with w2.container(border=True):
        ui.card_head("Operating Regime", "Which regime the turbine was in, hour by hour")
        rg = alt.Chart(s).mark_tick(thickness=3, size=26).encode(x=x, y=alt.Y("regime:N", sort=meta["regimes"], title=None), color=alt.Color("regime:N", scale=alt.Scale(domain=meta["regimes"], range=ui.SERIES[:4]), legend=None),
                                                                 tooltip=["regime", alt.Tooltip("ts:T")])
        ui.show(rg, 250)


ui.live_fragment(render)(tb, hours)

# ---- alert and failure log (changes slowly: outside the live fragment) --------------------------------------------------------------------------
h = api.get(f"/turbine/{tb}/history")
with st.container(border=True):
    ui.card_head("Historical Alerts & Failure Log", "Replayed year so far · alerts from the fused risk model and failures from the status log")
    events = []
    for a in h["alerts"]:
        kind = {"Failure confirmed": "crit", "Open": "warn", "False alarm": "muted"}.get(a["status"], "muted")
        events.append((pd.Timestamp(a["start"]), ui.badge(a["band"]), f"Risk alert · {a['hours']} h flagged · peak {ui.pct(a['peak_risk'], 0)}", ui.e(drivers_text(a["top_drivers"])), ui.pill(a["status"], kind)))
    for f_ in h["failures"]:
        warned = {1.0: ui.pill("warned in advance", "ok"), 0.0: ui.pill("missed", "crit")}.get(f_["warned_watch"], ui.pill("–", "muted"))
        events.append((pd.Timestamp(f_["t_fail"]), ui.pill("Failure", "crit", "error"), ui.e(f_["message"]), "recorded in the status log", warned))
    if events:
        events.sort(key=lambda e_: e_[0], reverse=True)
        rows = "".join(f'<tr><td class="wg-mono">{t:%d %b %Y %H:%M}</td><td>{sev}</td><td><b>{ev}</b></td><td style="font-size:.82rem">{det}</td><td>{out}</td></tr>' for t, sev, ev, det, out in events[:20])
        st.markdown(f'<table class="wg-table"><thead><tr><th>Time</th><th>Severity</th><th>Event</th><th>Sensors that moved / source</th><th>Outcome</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
        st.caption("Maintenance actions are not part of the project data, so none are shown.")
    else:
        st.info("No alerts or failures yet for this turbine in the replay.")
ui.disclaimer_note(meta)
