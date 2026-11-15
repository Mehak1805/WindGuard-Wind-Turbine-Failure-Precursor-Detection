"""WindGuard dashboard entry point.  Run:  streamlit run frontend/app.py   (backend must be running; see run_all.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import streamlit as st
import ui

st.set_page_config(page_title="WindGuard", page_icon="🌬️", layout="wide")
ui.setup("WindGuard")
ui.sidebar_clock()

pages = [
    st.Page("views/fleet.py", title="Fleet Overview", icon="🏭", default=True),
    st.Page("views/anomaly.py", title="Anomaly & Alerts", icon="🚨"),
    st.Page("views/risk.py", title="Turbine Risk", icon="🎯"),
    st.Page("views/explain.py", title="Explainability", icon="🔍"),
    st.Page("views/validation.py", title="Validation & Cross-Farm", icon="✅"),
    st.Page("views/turbine.py", title="Turbine Details", icon="🔧"),
]
ui.alert_banner()
st.navigation(pages).run()
