"""Start the backend (FastAPI, port 8000) and the dashboard (Streamlit, port 8501) with one command:  python run_all.py
Stop both with Ctrl+C."""
import os, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
api = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"], cwd=ROOT)
print("Starting backend ...")
for _ in range(60):                                   # wait until the API answers (it loads the data first)
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2); break
    except Exception:
        time.sleep(1)
else:
    api.terminate(); sys.exit("Backend did not start - see the error above.")
print("Backend ready -> http://127.0.0.1:8000/docs   |   Dashboard -> http://localhost:8501")
ui = subprocess.Popen([sys.executable, "-m", "streamlit", "run", os.path.join("frontend", "app.py"), "--server.port", "8501"], cwd=ROOT)
try:
    ui.wait()
except KeyboardInterrupt:
    pass
finally:
    ui.terminate(); api.terminate()
