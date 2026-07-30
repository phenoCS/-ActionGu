@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title 任务修仙计时器 · 启动器
:: 一键启动：检测/自动安装 Python 后运行 main.py
:: 若本机已装 Python 则直接运行；否则静默安装后再运行，用户无需任何手动操作。
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"
