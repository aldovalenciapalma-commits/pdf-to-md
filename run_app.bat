@echo off
set SCRIPT_DIR=%~dp0
"%SCRIPT_DIR%.venv\Scripts\python.exe" -m streamlit run "%SCRIPT_DIR%app.py" %*

