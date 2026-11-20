@echo off
title Indeed Automation - Job Monitor & AI Tailor
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python app_gui.py
pause
