"""Tiny client for the WindGuard backend. Every page gets its data through get() / post() - nothing is read from files here."""
import os
import requests
import streamlit as st

BASE = os.environ.get("WINDGUARD_API", "http://127.0.0.1:8000")


def get(path, **params):
    try:
        r = requests.get(BASE + path, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot reach the backend at {BASE}.  Start it first:  `python run_all.py`  "
                 f"(or in another terminal: `python -m uvicorn backend.main:app --port 8000`).")
        st.stop()
    except requests.exceptions.HTTPError as e:
        st.error(f"Backend error on {path}: {e.response.text[:300]}")
        st.stop()


def post(path, body):
    try:
        r = requests.post(BASE + path, json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Backend error on {path}: {e}")
        st.stop()
