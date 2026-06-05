@echo off
chcp 65001 >nul
title Import Mestre - Poker App
cd /d "%~dp0"
python run_all.py
echo.
pause
