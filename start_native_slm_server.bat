@echo off
title Ssense Sovereign SLM Server (Native GPU / CPU)
cd /d "%~dp0apps\slm-server"

echo ======================================================================
echo    Starting Ssense Native SLM Server on http://localhost:8000
echo    (No Docker Required - Powered by PyTorch + CUDA RTX 3060)
echo ======================================================================

set PYTHONIOENCODING=utf-8
set SSENSE_ENV=development

C:\Users\anubh\miniconda3\envs\torch_env\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

pause
