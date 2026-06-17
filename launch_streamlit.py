from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = Path(r"C:\Users\Kailash\anaconda3\python.exe")

process = subprocess.Popen(
    [str(PYTHON), "-m", "streamlit", "run", "app.py", "--server.port", "8501"],
    cwd=ROOT,
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)

print(process.pid)
