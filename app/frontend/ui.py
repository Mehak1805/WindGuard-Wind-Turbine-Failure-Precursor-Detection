"""Look and feel shared by all pages: colours, KPI cards, status badges, chart helpers, the live-clock sidebar."""
import altair as alt
import pandas as pd
import streamlit as st
import api

# ---- colours (validated palette: categorical slots 1-6, fixed status colours) ----------------------------------------------------
INK, MUTED, GRID = "#0f2a3d", "#52627a", "#e1e0d9"
BRAND, BRAND_DARK = "#2a78d6", "#184f95"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]          # always used in this order
BAND_COLOR = {"Low": "#0ca30c", "Watch": "#fab219", "High": "#d03b3b"}               # status colours: always paired with an icon + label
BAND_ICON = {"Low": "✓", "Watch": "▲", "High": "⬤"}
BAND_ORDER = ["Low", "Watch", "High"]


def setup(title, icon="🌬️"):
    """Page set-up + the CSS that gives the dashboard its card look."""
    st.markdown("""
<style>
.block-container {padding-top: 4rem; max-width: 1500px;}
.wg-hero {border-radius: 16px; padding: 22px 28px; color: #fff; margin-bottom: 14px;
          background: linear-gradient(110deg, #0d366b 0%, #1c5cab 55%, #2a78d6 100%);}
.wg-hero h1 {color:#fff; margin:0; font-size: 1.9rem;} .wg-hero p {margin: 4px 0 0 0; opacity:.9;}
.wg-kpi {background:#fff; border:1px solid #dbe3ef; border-radius: 14px; padding: 14px 16px; height: 100%;}
.wg-kpi .l {color:#52627a; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em;}
.wg-kpi .v {color:#0f2a3d; font-size:1.9rem; font-weight:700; line-height:1.15;} .wg-kpi .s {color:#52627a; font-size:.8rem;}
.wg-badge {display:inline-block; padding:2px 10px; border-radius: 999px; font-weight:600; font-size:.8rem;}
.wg-sim {display:inline-block; background:#fff3cd; color:#6b4e00; border:1px solid #f1d98a; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;}
.wg-live {display:inline-block; background:#e7f6e7; color:#006300; border:1px solid #b5e0b5; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;}
.wg-paused {display:inline-block; background:#eef1f6; color:#52627a; border:1px solid #d3dbe8; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:600;}
</style>""", unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="wg-hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="wg-kpi"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def badge(band):
    if band == "Offline":
        return '<span class="wg-badge" style="background:#d3dbe8;color:#0f2a3d">○ Offline</span>'
    fg = "#0b0b0b" if band == "Watch" else "#ffffff"
    return f'<span class="wg-badge" style="background:{BAND_COLOR[band]};color:{fg}">{BAND_ICON[band]} {band}</span>'


def pct(x, nd=1):
    return "–" if x is None else f"{100 * x:.{nd}f}%"


def live_fragment(fn, seconds=3):
    """Wrap a render function so it re-runs every few seconds (the live replay) unless the sidebar toggle is off."""
    return st.fragment(run_every=(seconds if st.session_state.get("auto_refresh", True) else None))(fn)


# ---- charts -------------------------------------------------------------------------------------------------------------------------
def style(chart, height=260):
    return (chart.properties(height=height)
            .configure_view(strokeWidth=0)
            .configure_axis(labelOverlap=False, gridColor=GRID, domainColor="#c3c2b7", labelColor=MUTED, titleColor=MUTED, labelFontSize=11, titleFontSize=11)
            .configure_legend(labelColor=INK, titleColor=MUTED, orient="bottom"))


def show(chart, height=260):
    st.altair_chart(style(chart, height), width="stretch")


def band_scale():
    return alt.Scale(domain=BAND_ORDER, range=[BAND_COLOR[b] for b in BAND_ORDER])


def gauge(value, watch, high):
    """Half-circle gauge of a probability (0-1) with the Watch / High thresholds marked."""
    import math
    ang = lambda v: -math.pi / 2 + math.pi * v
    seg = pd.DataFrame([dict(a=ang(0), b=ang(watch), band="Low"), dict(a=ang(watch), b=ang(high), band="Watch"), dict(a=ang(high), b=ang(1), band="High")])
    base = alt.Chart(seg).mark_arc(innerRadius=62, outerRadius=88, opacity=0.35).encode(
        theta=alt.Theta("a:Q", scale=alt.Scale(domain=[-math.pi / 2, math.pi / 2], range=[-math.pi / 2, math.pi / 2])), theta2="b:Q",
        color=alt.Color("band:N", scale=band_scale(), legend=None))
    cur = pd.DataFrame([dict(a=ang(0), b=ang(max(value, 0.004)))])
    fill = alt.Chart(cur).mark_arc(innerRadius=62, outerRadius=88, color=INK).encode(theta="a:Q", theta2="b:Q")
    txt = alt.Chart(pd.DataFrame([dict(t=f"{100 * value:.1f}%")])).mark_text(fontSize=34, fontWeight="bold", color=INK, dy=-8).encode(text="t:N")
    return alt.layer(base, fill, txt).properties(width=230, height=140).configure_view(strokeWidth=0)


# ---- sidebar: live clock (shared by every page) ---------------------------------------------------------------------------------------
SPEEDS = {"1 h / s": 1, "6 h / s": 6, "12 h / s": 12, "1 day / s": 24, "3 days / s": 72, "1 week / s": 168}


def sidebar_clock():
    st.sidebar.markdown("### 🌬️ WindGuard")
    st.sidebar.caption("Failure-precursor monitoring · Kelmarsh-style SCADA")

    @st.fragment(run_every=(2 if st.session_state.get("auto_refresh", True) else None))
    def clock():
        s = api.get("/live/state")
        tag = '<span class="wg-live">● LIVE REPLAY</span>' if s["playing"] else '<span class="wg-paused">❚❚ PAUSED</span>'
        st.markdown(f'{tag} <span class="wg-sim">SIMULATION</span>', unsafe_allow_html=True)
        st.markdown(f"**{s['sim_time']}**")
        st.progress(min(max(s["progress"], 0.0), 1.0))
    with st.sidebar:
        clock()
        c1, c2 = st.columns(2)
        s = api.get("/live/state")
        if c1.button("❚❚ Pause" if s["playing"] else "▶ Play", width="stretch"):
            api.post("/live/control", dict(action="pause" if s["playing"] else "play")); st.rerun()
        if c2.button("⏭ Next alert", width="stretch"):
            api.post("/live/control", dict(action="next_alert")); st.rerun()
        cur = next((k for k, v in SPEEDS.items() if v == s["speed_hours_per_second"]), "12 h / s")
        choice = st.select_slider("Replay speed", options=list(SPEEDS), value=cur)
        if SPEEDS[choice] != s["speed_hours_per_second"]:
            api.post("/live/control", dict(action="speed", value=SPEEDS[choice])); st.rerun()
        st.toggle("Auto-refresh pages", value=True, key="auto_refresh")
        if st.button("↺ Restart replay", width="stretch"):
            api.post("/live/control", dict(action="reset")); st.rerun()
        st.divider()


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
            st.success("No active alerts. All turbines are operating normally.")
            return
        if kind == "failed":
            box = st.error
            txt = (f"**Failure confirmed on Turbine {int(pick['turbine_id'])}**\n\n"
                   f"{pick['fault']} at {pick['t_fail']:%d %b %Y, %H:%M}. "
                   f"The system raised an alert {pick['lead_days']:.1f} days before the failure.")
        else:
            box = st.error if kind == "High" else st.warning
            txt = (f"**{kind} alert on Turbine {int(pick['turbine_id'])}**\n\n"
                   f"Risk score {pick['peak_risk']:.2f}, first flagged {pd.Timestamp(pick['start']):%d %b %Y, %H:%M}.")
        c1, c2 = st.columns([6, 1], vertical_alignment="center")
        with c1:
            box(txt)
        if c2.button("View turbine", key="banner_open", width="stretch"):
            st.session_state["turbine_sel"] = int(pick["turbine_id"])
            st.switch_page("views/turbine.py")
    banner()
