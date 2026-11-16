"""Look and feel shared by all pages (modelled on the WindGuard mock-ups): sidebar, page header, cards, KPI tiles, pills, bars, dial, donut, live clock.

Rule for every page: only show numbers that come from the backend (= from the notebook's export). Nothing here invents data.
"""
import html
import math
import altair as alt
import pandas as pd
import streamlit as st
import api

# ---- colours ------------------------------------------------------------------------------------------------------------------------
INK, MUTED, GRID, LINE = "#0f2a3d", "#5b6b80", "#e6ebf2", "#e4eaf2"
TEAL, TEAL_DARK = "#0e5a6b", "#0a4553"
BRAND, BRAND_DARK = "#2a78d6", "#184f95"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]          # categorical colours, always used in this order
BAND_COLOR = {"Low": "#0ca30c", "Watch": "#fab219", "High": "#d03b3b", "Offline": "#9aa7b8"}
BAND_LABEL = {"Low": "Nominal", "Watch": "Observation", "High": "Critical", "Offline": "Offline"}
BAND_ICON = {"Low": "✓", "Watch": "▲", "High": "●", "Offline": "○"}
BAND_ORDER = ["Low", "Watch", "High"]
BAND_KIND = {"Low": "ok", "Watch": "warn", "High": "crit", "Offline": "muted"}


def tname(tb):
    """Display name of a Kelmarsh turbine, e.g. 4 -> KLM-04."""
    return f"KLM-{int(tb):02d}"


# ---- global CSS --------------------------------------------------------------------------------------------------------------------
CSS = """
<style>
:root {--ink:#0f2a3d; --muted:#5b6b80; --line:#e4eaf2; --bg:#f3f6fa; --teal:#0e5a6b; --blue:#2a78d6;}
.stApp {background: var(--bg);}
.wg-top, .wg-kpi, .wg-hero, .wg-stat, .wg-sline, table.wg-table, .wg-ch, .wg-th, .wg-pill, .wg-brand, .wg-note, .wg-warnbox, .wg-barrow {font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif;}
[data-testid="stIconMaterial"] {font-family: "Material Symbols Rounded" !important;}
[data-testid="stMarkdownContainer"] p {margin-bottom: .25rem;}
header[data-testid="stHeader"] {background: transparent; height: 2.2rem;}
[data-testid="stToolbar"], .stAppDeployButton, #MainMenu, [data-testid="stToastContainer"], [data-testid="stToast"], [data-testid="stSkillsNudge"], [data-testid="stSkillsNudgeAnchor"] {display: none !important;}
.block-container {padding: 1.2rem 2rem 3rem 2rem; max-width: 1560px;}
h1, h2, h3, h4 {color: var(--ink); letter-spacing: -0.01em;}

/* sidebar */
[data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid var(--line);}
[data-testid="stSidebar"] > div:first-child {padding-top: .4rem;}
[data-testid="stSidebarHeader"] {padding: .4rem .6rem 0 .6rem; min-height: 1.6rem;}
[data-testid="stSidebarUserContent"] {padding: .2rem 1rem 1rem 1rem;}
.wg-brand {display:flex; align-items:center; gap:10px; margin: 0 0 14px 2px;}
.wg-brand .logo {width:38px; height:38px; border-radius:11px; background: linear-gradient(135deg,#0e5a6b,#2a78d6); color:#fff; display:flex; align-items:center; justify-content:center; font-size:22px;}
.wg-brand .name {font-weight:800; color:var(--ink); font-size:1.15rem; line-height:1.05;} .wg-brand .sub {color:var(--muted); font-size:.62rem; letter-spacing:.12em; font-weight:700;}
[data-testid="stPageLink-NavLink"] {border-radius: 10px; padding: .5rem .75rem; margin: 1px 0; color: #3b4d63;}
[data-testid="stPageLink-NavLink"] p {font-size: .93rem; font-weight: 600;}
[data-testid="stPageLink-NavLink"]:hover {background: #eef3fa;}
[data-testid="stPageLink-NavLink"][aria-current="page"] {background: #e3effd; color: #1c5cab;}
[data-testid="stPageLink-NavLink"][aria-current="page"] p {color: #1c5cab;}
.wg-sidehead {color:#8a97a8; font-size:.68rem; font-weight:800; letter-spacing:.12em; margin: 14px 0 6px 4px;}

/* cards = bordered containers */
div[data-testid="stVerticalBlockBorderWrapper"] {background:#fff; border:1px solid var(--line) !important; border-radius:16px !important; box-shadow: 0 1px 2px rgba(15,42,61,.04);}
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {box-shadow:none; border-radius:12px !important; background:#fbfcfe;}
[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {background:#f8fafd;}
.wg-ch {margin: 2px 0 10px 0;} .wg-ct {color: var(--ink); font-weight:700; font-size:1.02rem;} .wg-cs {color: var(--muted); font-size:.78rem; margin-top:1px;}

/* page header */
.wg-top {display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; margin: 0 0 14px 0;}
.wg-crumb {color:#8a97a8; font-size:.72rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;}
.wg-top h1 {margin:2px 0 2px 0; font-size:1.9rem; font-weight:800; padding:0;} .wg-top p {margin:0; color:var(--muted); font-size:.92rem; max-width: 760px;}
.wg-chips {display:flex; gap:8px; flex-wrap:wrap; align-items:center; justify-content:flex-end;}

/* pills */
.wg-pill {display:inline-flex; align-items:center; gap:5px; padding:3px 11px; border-radius:999px; font-weight:700; font-size:.74rem; white-space:nowrap;}
.wg-pill.ok {background:#e6f6e6; color:#00600a;} .wg-pill.warn {background:#fff1cc; color:#7a5200;} .wg-pill.crit {background:#fde4e4; color:#a11f1f;}
.wg-pill.info {background:#e3effd; color:#1c5cab;} .wg-pill.muted {background:#eaeef4; color:#52627a;} .wg-pill.dark {background:#0e5a6b; color:#fff;}
.wg-pill.live {background:#e6f6e6; color:#00600a;} .wg-pill.paused {background:#eaeef4; color:#52627a;}

/* KPI tiles */
.wg-kpi {background:#fff; border:1px solid var(--line); border-radius:16px; padding:14px 16px; height:100%; margin-bottom:8px; box-shadow: 0 1px 2px rgba(15,42,61,.04);}
.wg-kpi .top {display:flex; justify-content:space-between; align-items:center;}
.wg-kpi .lab {color:#6b7a8f; font-size:.68rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase;}
.wg-kpi .val {color:var(--ink); font-size:1.85rem; font-weight:800; line-height:1.2; margin-top:4px;} .wg-kpi .sub {color:var(--muted); font-size:.78rem; margin-top:2px;}
.wg-ico {width:30px; height:30px; border-radius:9px; display:flex; align-items:center; justify-content:center;}
.wg-ico.blue {background:#e3effd; color:#1c5cab;} .wg-ico.red {background:#fde4e4; color:#a11f1f;} .wg-ico.green {background:#e6f6e6; color:#00600a;}
.wg-ico.amber {background:#fff1cc; color:#7a5200;} .wg-ico.teal {background:#dff1f4; color:#0e5a6b;}
.msi {font-family:"Material Symbols Rounded"; font-weight:normal; font-style:normal; font-size:19px; line-height:1; letter-spacing:normal; text-transform:none; display:inline-block; white-space:nowrap; -webkit-font-feature-settings:"liga"; font-feature-settings:"liga";}

/* hero + small stat boxes */
.wg-hero {border-radius:16px; padding:20px 22px 18px 22px; color:#fff; min-height: 318px; display:flex; flex-direction:column; justify-content:space-between;
          background: linear-gradient(120deg,#0a4553 0%,#0e5a6b 45%,#2a78d6 100%); background-size:cover; background-position:center;}
.wg-hero .t {font-size:1.35rem; font-weight:800;} .wg-hero .s {opacity:.88; font-size:.86rem; margin-top:2px;}
.wg-hero .row {display:flex; gap:12px; flex-wrap:wrap; margin-top:14px;}
.wg-hero .box {background:rgba(255,255,255,.95); color:var(--ink); border-radius:14px; padding:10px 16px; min-width:150px; flex:1;}
.wg-hero .box .l {color:#6b7a8f; font-size:.64rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase;} .wg-hero .box .v {font-size:1.7rem; font-weight:800; line-height:1.15;} .wg-hero .box .u {color:#6b7a8f; font-size:.76rem;}
.wg-stat {background:#f6f9fd; border:1px solid var(--line); border-radius:12px; padding:10px 12px; height:100%; margin-bottom:6px;}
.wg-stat .l {color:#6b7a8f; font-size:.66rem; font-weight:800; letter-spacing:.07em; text-transform:uppercase;} .wg-stat .v {color:var(--ink); font-size:1.35rem; font-weight:800; line-height:1.2;} .wg-stat .s {color:var(--muted); font-size:.74rem;}
.wg-sline {display:flex; justify-content:space-between; align-items:center; gap:10px; padding:7px 0; border-bottom:1px solid #eef2f7; font-size:.86rem; color:var(--ink);}
.wg-sline:last-child {border-bottom:none;} .wg-sline .m {color:var(--muted); font-size:.78rem;}
.wg-legend {display:flex; align-items:center; gap:8px; font-size:.84rem; color:var(--ink);} .wg-dot {width:10px; height:10px; border-radius:50%; display:inline-block;}

/* bars */
.wg-bar {background:#e8edf4; border-radius:999px; height:8px; width:100%; overflow:hidden;} .wg-bar > i {display:block; height:100%; border-radius:999px;}
.wg-barrow {display:flex; align-items:center; gap:10px;} .wg-barrow .n {min-width:52px; white-space:nowrap; text-align:right; font-weight:700; color:var(--ink); font-size:.85rem;}

/* html tables */
table.wg-table {width:100%; border-collapse:collapse; font-size:.86rem;} table.wg-table th {text-align:left; color:#6b7a8f; font-size:.66rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; padding:8px 10px; border-bottom:1px solid var(--line);}
table.wg-table td {padding:10px 10px; border-bottom:1px solid #eef2f7; color:var(--ink); vertical-align:middle;} table.wg-table tr:last-child td {border-bottom:none;}
.wg-mono {font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size:.8rem; color:#3b4d63; white-space:nowrap;}
table.wg-table td.nw {white-space:nowrap;}
.wg-note {background:#eef5fd; border:1px solid #d5e5f8; color:#1c4f8a; border-radius:12px; padding:10px 14px; font-size:.82rem;}
.wg-warnbox {background:#fff8e1; border:1px solid #f1d98a; color:#6b4e00; border-radius:12px; padding:9px 14px; font-size:.8rem;}

.wg-th {color:#6b7a8f; font-size:.64rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; padding:6px 0; border-bottom:1px solid var(--line); margin-bottom:4px;}
hr.wg-hr {border:none; border-top:1px solid #eef2f7; margin:2px 0;}

/* buttons */
button[kind="primary"], [data-testid="stBaseButton-primary"] {background:#0e5a6b !important; border-color:#0e5a6b !important; color:#fff !important; border-radius:10px !important; font-weight:700 !important;}
button[kind="secondary"], [data-testid="stBaseButton-secondary"] {border-radius:10px !important; font-weight:600 !important; border-color:#d3dbe8 !important;}
[data-testid="stSegmentedControl"] button {font-size:.8rem;}
[data-testid="stSidebar"] .stButton button {padding:.3rem .35rem; font-size:.78rem; white-space:nowrap;}
[data-testid="stSidebar"] .stButton button p {font-size:.78rem; white-space:nowrap; overflow:visible;}
[data-testid="stMetric"] {background:#f6f9fd; border:1px solid var(--line); border-radius:12px; padding:8px 12px;}
</style>
"""


def setup():
    st.markdown(CSS, unsafe_allow_html=True)


# ---- layout pieces ---------------------------------------------------------------------------------------------------------------------
def e(x):
    return html.escape(str(x))


def icon(name, tone="blue"):
    return f'<span class="wg-ico {tone}"><span class="msi">{name}</span></span>'


def pill(text, kind="info", ico=None):
    i = f'<span class="msi" style="font-size:14px">{ico}</span>' if ico else ""
    return f'<span class="wg-pill {kind}">{i}{e(text)}</span>'


def page_header(crumb, title, subtitle, chips=""):
    st.markdown(f'<div class="wg-top"><div><div class="wg-crumb">Dashboard › Fleet Operations › {e(crumb)}</div><h1>{e(title)}</h1><p>{e(subtitle)}</p></div>'
                f'<div class="wg-chips">{chips}</div></div>', unsafe_allow_html=True)


def card_head(title, sub="", right=""):
    s = f'<div class="wg-cs">{e(sub)}</div>' if sub else ""
    st.markdown(f'<div class="wg-ch"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px"><div><div class="wg-ct">{e(title)}</div>{s}</div><div>{right}</div></div></div>',
                unsafe_allow_html=True)


def kpi(col, label, value, sub="", ico="analytics", tone="blue"):
    col.markdown(f'<div class="wg-kpi"><div class="top"><span class="lab">{e(label)}</span>{icon(ico, tone)}</div><div class="val">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def stat(label, value, sub=""):
    return f'<div class="wg-stat"><div class="l">{e(label)}</div><div class="v">{value}</div><div class="s">{sub}</div></div>'


def bar(value, vmax=1.0, color=BRAND):
    w = 0 if value is None or vmax == 0 else max(0.0, min(1.0, value / vmax)) * 100
    return f'<div class="wg-bar"><i style="width:{w:.0f}%;background:{color}"></i></div>'


def barrow(value, vmax, color, text):
    return f'<div class="wg-barrow">{bar(value, vmax, color)}<span class="n">{text}</span></div>'


def badge(band):
    """Risk band as a pill with icon + label (colour is never the only signal)."""
    return f'<span class="wg-pill {BAND_KIND[band]}">{BAND_ICON[band]} {BAND_LABEL[band]}</span>'


def pct(x, nd=1):
    return "–" if x is None else f"{100 * x:.{nd}f}%"


def disclaimer_note(meta):
    st.markdown(f'<div class="wg-warnbox"><b>Data note.</b> {e(meta["run_info"]["disclaimer"])}</div>', unsafe_allow_html=True)


def go_turbine(tb):
    st.session_state["turbine_sel"] = int(tb)
    st.switch_page("views/turbine.py")


def live_fragment(fn, seconds=3):
    """Wrap a render function so it re-runs every few seconds (the live replay) unless the sidebar toggle is off."""
    return st.fragment(run_every=(seconds if st.session_state.get("auto_refresh", True) else None))(fn)


# ---- charts -------------------------------------------------------------------------------------------------------------------------
def style(chart, height=260):
    return (chart.properties(height=height)
            .configure_view(strokeWidth=0)
            .configure_axis(labelOverlap=False, gridColor=GRID, domainColor="#c9d2de", tickColor="#c9d2de", labelColor=MUTED, titleColor=MUTED, labelFontSize=11, titleFontSize=11)
            .configure_legend(labelColor=INK, titleColor=MUTED, orient="bottom", labelFontSize=11))


def show(chart, height=260):
    st.altair_chart(style(chart, height), width="stretch")


def tx(fmt="%d %b %H:%M", n=5):
    """Time axis with a few readable labels instead of one per hour."""
    return alt.Axis(format=fmt, tickCount=n, labelAngle=0, labelOverlap="greedy")


def band_scale():
    return alt.Scale(domain=BAND_ORDER, range=[BAND_COLOR[b] for b in BAND_ORDER])


def threshold_rules(watch, high):
    d = pd.DataFrame(dict(y=[watch, high], c=[BAND_COLOR["Watch"], BAND_COLOR["High"]]))
    return alt.Chart(d).mark_rule(strokeDash=[5, 4], strokeWidth=1.4).encode(y="y:Q", color=alt.Color("c:N", scale=None, legend=None))


def donut(parts, center_top, center_bottom, size=190):
    """parts: list of (label, value, colour). Ring with the total in the middle."""
    d = pd.DataFrame(parts, columns=["label", "value", "color"])
    if d["value"].sum() == 0:
        d = pd.DataFrame([("none", 1, "#e8edf4")], columns=["label", "value", "color"])
    arc = alt.Chart(d).mark_arc(innerRadius=size * 0.32, outerRadius=size * 0.47, stroke="#ffffff", strokeWidth=3, cornerRadius=3).encode(
        theta=alt.Theta("value:Q", stack=True), color=alt.Color("color:N", scale=None), order=alt.Order("label:N", sort="ascending"), tooltip=["label", "value"])
    t1 = alt.Chart(pd.DataFrame([dict(t=str(center_top))])).mark_text(fontSize=30, fontWeight="bold", color=INK, dy=-6).encode(text="t:N")
    t2 = alt.Chart(pd.DataFrame([dict(t=str(center_bottom))])).mark_text(fontSize=11, color=MUTED, dy=16).encode(text="t:N")
    return (arc + t1 + t2).properties(width=size, height=size).configure_view(strokeWidth=0)


TAU = alt.Scale(domain=[0, 2 * math.pi], range=[0, 2 * math.pi])


def dial(value, color, label="", size=210):
    """Full-circle dial of a probability (0-1): coloured arc over a grey ring, the percentage in the middle."""
    v = max(0.0, min(1.0, value))
    ring = alt.Chart(pd.DataFrame([dict(a=0, b=2 * math.pi)])).mark_arc(innerRadius=size * 0.36, outerRadius=size * 0.47, color="#e8edf4").encode(theta=alt.Theta("a:Q", scale=TAU), theta2="b:Q")
    fill = alt.Chart(pd.DataFrame([dict(a=0, b=max(v, 0.004) * 2 * math.pi)])).mark_arc(innerRadius=size * 0.36, outerRadius=size * 0.47, color=color, cornerRadius=6).encode(theta=alt.Theta("a:Q", scale=TAU), theta2="b:Q")
    t1 = alt.Chart(pd.DataFrame([dict(t=f"{100 * v:.1f}%")])).mark_text(fontSize=30, fontWeight="bold", color=INK, dy=-6).encode(text="t:N")
    t2 = alt.Chart(pd.DataFrame([dict(t=label)])).mark_text(fontSize=11, color=MUTED, dy=16).encode(text="t:N")
    return (ring + fill + t1 + t2).properties(width=size, height=size).configure_view(strokeWidth=0)


# ---- sidebar: brand, navigation, live-replay clock, data note --------------------------------------------------------------------------
SPEEDS = {"1 h / s": 1, "6 h / s": 6, "12 h / s": 12, "1 day / s": 24, "3 days / s": 72, "1 week / s": 168}


def sidebar(pages):
    with st.sidebar:
        st.markdown('<div class="wg-brand"><div class="logo"><span class="msi" style="font-size:24px">wind_power</span></div>'
                    '<div><div class="name">WindGuard</div><div class="sub">PREDICTIVE SCADA</div></div></div>', unsafe_allow_html=True)
        for p in pages:
            st.page_link(p)
        st.markdown('<div class="wg-sidehead">LIVE REPLAY</div>', unsafe_allow_html=True)
        sidebar_clock()


def sidebar_clock():
    @st.fragment(run_every=(2 if st.session_state.get("auto_refresh", True) else None))
    def clock():
        s = api.get("/live/state")
        tag = pill("LIVE REPLAY", "live", "play_arrow") if s["playing"] else pill("PAUSED", "paused", "pause")
        st.markdown(tag, unsafe_allow_html=True)
        st.markdown(f"**{s['sim_time']}**")
        st.progress(min(max(s["progress"], 0.0), 1.0))
    with st.container(border=True):
        clock()
        c1, c2 = st.columns(2)
        s = api.get("/live/state")
        if c1.button("Pause" if s["playing"] else "Play", width="stretch", icon=":material/pause:" if s["playing"] else ":material/play_arrow:"):
            api.post("/live/control", dict(action="pause" if s["playing"] else "play")); st.rerun()
        if c2.button("Next", width="stretch", icon=":material/skip_next:", help="Jump to the next alert in the replay"):
            api.post("/live/control", dict(action="next_alert")); st.rerun()
        cur = next((k for k, v in SPEEDS.items() if v == s["speed_hours_per_second"]), "12 h / s")
        choice = st.select_slider("Replay speed", options=list(SPEEDS), value=cur)
        if SPEEDS[choice] != s["speed_hours_per_second"]:
            api.post("/live/control", dict(action="speed", value=SPEEDS[choice])); st.rerun()
        st.toggle("Auto-refresh pages", value=True, key="auto_refresh")
        if st.button("Restart replay", width="stretch", icon=":material/restart_alt:"):
            api.post("/live/control", dict(action="reset")); st.rerun()
    st.caption("The 2022 test year is replayed as if it were arriving now. Nothing after the replay time is ever shown.")


def header_chips(meta, extra=""):
    """Chips shown top-right on every page: farm, replay time and the data-origin note."""
    s = api.get("/live/state")
    live = pill("Live replay", "live", "play_arrow") if s["playing"] else pill("Paused", "paused", "pause")
    return pill(f"Kelmarsh · {len(meta['turbines'])} turbines", "info", "wind_power") + live + extra + pill("Data origin unconfirmed", "warn", "info")


# ---- global alert banner (shown above every page) ---------------------------------------------------------------------------------------
def alert_banner():
    """Fleet-wide status strip: the most serious active alert (or the latest confirmed failure), whatever turbine/page is open."""
    @st.fragment(run_every=(3 if st.session_state.get("auto_refresh", True) else None))
    def banner():
        t = pd.Timestamp(api.get("/live/state")["sim_time"])
        al = api.get("/alerts", limit=60)
        df = pd.DataFrame(al) if al else pd.DataFrame()
        pick, kind = None, "ok"
        if len(df):
            df["t_fail"] = pd.to_datetime(df["t_fail"], errors="coerce")
            fails = df[df["status"] == "Failure confirmed"]
            fails = fails[(t - fails["t_fail"]) <= pd.Timedelta(hours=48)]
            act = df[df["active"] & (df["status"] == "Open")]
            if len(fails):
                pick, kind = fails.sort_values("t_fail").iloc[-1], "failed"
            elif len(act):
                act = act.assign(_h=(act["band"] == "High").astype(int)).sort_values(["_h", "peak_risk"])
                pick, kind = act.iloc[-1], act.iloc[-1]["band"]
        if kind == "ok":
            return                                                      # nothing to flag: no banner (the page itself shows the status)
        if kind == "failed":
            box = st.error
            txt = (f"**Failure confirmed on {tname(pick['turbine_id'])}**: {pick['fault']} at {pick['t_fail']:%d %b %Y, %H:%M}. "
                   f"The system raised an alert {pick['lead_days']:.1f} days before the failure.")
        else:
            box = st.error if kind == "High" else st.warning
            txt = f"**{BAND_LABEL[kind]} alert on {tname(pick['turbine_id'])}**: risk score {pick['peak_risk']:.2f}, first flagged {pd.Timestamp(pick['start']):%d %b %Y, %H:%M}."
        c1, c2 = st.columns([6, 1], vertical_alignment="center")
        with c1:
            box(txt)
        if c2.button("View turbine", key="banner_open", width="stretch"):
            go_turbine(pick["turbine_id"])
    banner()
