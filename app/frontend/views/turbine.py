"""Page 6 - Turbine Details: one turbine's live sensors, risk, regime, failure history and alerts."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # lets the page import api / ui
import altair as alt
import pandas as pd
import streamlit as st
import api, ui

ui.setup("Turbine Details")
meta = api.get("/meta")
ui.hero("Turbine Details", "Everything about one turbine: risk, temperatures, pressures, operating regime and its failure history.")
c1, c2 = st.columns([1, 2])
tb = c1.selectbox("Turbine", meta["turbines"], format_func=lambda t: f"Turbine {t}", key="turbine_sel")
hours = c2.select_slider("Window", options=[24, 72, 168, 336, 720], value=168, format_func=lambda h: f"last {h // 24} day{'s' if h > 24 else ''}")


def render(tb, hours):
    d = api.get(f"/turbine/{tb}/series", hours=hours)
    s = pd.DataFrame(d["series"]); f = pd.DataFrame(d["failures"])
    if s.empty:
        st.info("No data yet for this window."); return
    s["ts"] = pd.to_datetime(s["ts"]); last = s.iloc[-1]
    c = st.columns(5)
    ui.kpi(c[0], "Risk now", ui.pct(last["risk"]), f"band: {last['band']}")
    ui.kpi(c[1], "Regime", last["regime"], "K-Means on wind & power")
    ui.kpi(c[2], "Wind / power", f"{last['Wind speed (m/s)']:.1f} m/s", f"{last['Power (kW)']:.0f} kW")
    ui.kpi(c[3], "Gear oil temp", f"{last['Gear oil temperature (°C)']:.1f} °C", f"ambient {last['Nacelle ambient temperature (°C)']:.1f} °C")
    ui.kpi(c[4], "Deviation score", f"{last['dev_norm']:.2f}", "1.0 = 99th pct of healthy")

    def marks(ch):
        if len(f):
            fm = alt.Chart(f.assign(t_fail=pd.to_datetime(f["t_fail"]))).mark_rule(color=ui.BAND_COLOR["High"], strokeWidth=2).encode(x="t_fail:T", tooltip=["message", "t_fail"])
            return ch + fm
        return ch
    x = alt.X("ts:T", title=None, scale=alt.Scale(domain=[s["ts"].min(), s["ts"].max()]))
    st.markdown("#### Fused failure risk")
    th = meta["thresholds"]
    risk = alt.Chart(s).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK, strokeWidth=2)).encode(x=x, y=alt.Y("risk:Q", scale=alt.Scale(domain=[0, 1]), title="risk"), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("risk:Q", format=".2f"), "band"])
    rules = alt.Chart(pd.DataFrame(dict(y=[th["watch"], th["high"]]))).mark_rule(strokeDash=[4, 4], color=ui.MUTED).encode(y="y:Q")
    ui.show(marks(risk + rules), 190)
    if len(f): st.caption("Red vertical lines mark failures that have already happened.")

    def lines(cols, title, height=190):
        long = s.melt(id_vars="ts", value_vars=cols, var_name="sensor", value_name="v")
        long["sensor"] = long["sensor"].str.replace(r" \(.*\)", "", regex=True)
        ch = alt.Chart(long).mark_line(strokeWidth=1.8).encode(x=x, y=alt.Y("v:Q", title=title, scale=alt.Scale(zero=False)), color=alt.Color("sensor:N", scale=alt.Scale(range=ui.SERIES), legend=alt.Legend(orient="bottom", title=None, columns=2, labelLimit=320)),
                                                               tooltip=["sensor", alt.Tooltip("ts:T"), alt.Tooltip("v:Q", format=".1f")])
        ui.show(marks(ch), height)
    a, b = st.columns(2)
    with a:
        st.markdown("#### Temperatures (°C)")
        lines(["Gear oil temperature (°C)", "Front bearing temperature (°C)", "Generator bearing front temperature (°C)", "Stator temperature 1 (°C)", "Nacelle ambient temperature (°C)"], "°C", 230)
    with b:
        st.markdown("#### Pressures (bar)")
        lines(["Gear oil inlet pressure (bar)", "Hydraulic oil pressure (bar)"], "bar", 230)
    a, b = st.columns(2)
    with a:
        st.markdown("#### Power (kW)")
        pw = alt.Chart(s).mark_area(color="#cde2fb", line=dict(color=ui.BRAND_DARK)).encode(x=x, y=alt.Y("Power (kW):Q", title="kW"), tooltip=[alt.Tooltip("ts:T"), alt.Tooltip("Power (kW):Q", format=".0f"), "regime"])
        ui.show(pw, 170)
    with b:
        st.markdown("#### Operating regime")
        rg = alt.Chart(s).mark_tick(thickness=3, size=26).encode(x=x, y=alt.Y("regime:N", sort=meta["regimes"], title=None), color=alt.Color("regime:N", scale=alt.Scale(domain=meta["regimes"], range=ui.SERIES[:4]), legend=None), tooltip=["regime", alt.Tooltip("ts:T")])
        ui.show(rg, 170)

    st.markdown("#### Latest condition-sensor deviation (vs this turbine's healthy behaviour in the same regime)")
    z = pd.DataFrame(dict(sensor=[k.replace(" (", " · ").rstrip(")") for k in d["latest_z"]], z=list(d["latest_z"].values())))
    ch = alt.Chart(z).mark_bar().encode(y=alt.Y("sensor:N", sort=None, title=None, axis=alt.Axis(labelLimit=260)), x=alt.X("z:Q", title="robust z-score"),
                                        color=alt.condition(alt.datum.z > 0, alt.value("#2a78d6"), alt.value("#d03b3b")), tooltip=["sensor", alt.Tooltip("z:Q", format=".2f")])
    ui.show(ch, 170)


ui.live_fragment(render)(tb, hours)

h = api.get(f"/turbine/{tb}/history")
st.markdown("#### Failure and alert history (replayed year so far)")
l, r = st.columns(2)
with l:
    st.markdown("**Failures**")
    fl = pd.DataFrame(h["failures"])
    if len(fl):
        fl["t_fail"] = pd.to_datetime(fl["t_fail"]).dt.strftime("%b %d %Y %H:%M")
        fl["Warned"] = fl["warned_watch"].map({1.0: "✓ yes", 0.0: "✗ missed"}).fillna("–")
        st.dataframe(fl[["t_fail", "message", "Warned"]].rename(columns={"t_fail": "Failed at", "message": "Failure"}), hide_index=True, width="stretch")
    else:
        st.caption("No failures yet in the replay.")
with r:
    st.markdown("**Alerts**")
    al = pd.DataFrame(h["alerts"])
    if len(al):
        al["start"] = pd.to_datetime(al["start"]).dt.strftime("%b %d %H:%M")
        st.dataframe(al[["start", "band", "hours", "peak_risk", "status", "lead_days"]].rename(columns={"start": "Start", "band": "Band", "hours": "Hours", "peak_risk": "Peak risk", "status": "Outcome", "lead_days": "Lead (d)"}),
                     hide_index=True, width="stretch", column_config={"Peak risk": st.column_config.NumberColumn(format="%.2f"), "Lead (d)": st.column_config.NumberColumn(format="%.1f")})
    else:
        st.caption("No alerts yet.")
