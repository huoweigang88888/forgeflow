@echo off
set APP_ENV=development
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set NO_PROXY=127.0.0.1,localhost,::1
set no_proxy=127.0.0.1,localhost,::1

echo Starting ForgeFlow API...
f:\AI_Forgeflow\forgeflow\apps\api\.venv\Scripts\python.exe -m uvicorn forgeflow.main:app --host 127.0.0.1 --port 8000 --log-level warning
