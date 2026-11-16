"""WindGuard dashboard entry point.  Run:  streamlit run frontend/app.py   (backend must be running; see run_all.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit as st
import ui

st.set_page_config(page_title="WindGuard · Predictive SCADA", page_icon=":material/wind_power:", layout="wide")
ui.setup()

pages = [
    st.Page("views/fleet.py", title="Fleet Overview", icon=":material/space_dashboard:", default=True),
    st.Page("views/anomaly.py", title="Anomaly & Alerts", icon=":material/warning:"),
    st.Page("views/risk.py", title="Turbine Risk", icon=":material/monitoring:"),
    st.Page("views/explain.py", title="Explainability & Models", icon=":material/lightbulb:"),
    st.Page("views/validation.py", title="Validation & Cross-Farm", icon=":material/verified:"),
    st.Page("views/turbine.py", title="Turbine Details", icon=":material/wind_power:"),
]
current = st.navigation(pages, position="hidden")       # our own sidebar (ui.sidebar) draws the navigation links
ui.sidebar(pages)
ui.alert_banner()
current.run()
