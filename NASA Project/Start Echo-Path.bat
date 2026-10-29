@echo off
cd /d "%~dp0"
python -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
if errorlevel 1 (
    echo Install dependencies with: python -m pip install -r requirements.txt
    pause
)
