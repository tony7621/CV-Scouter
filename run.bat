@echo off
echo 🚀 正在啟動 FastAPI 後端...
start cmd /k "uvicorn main:app --reload --port 8000"

:: 等待 3 秒確保後端啟動
timeout /t 3 /nobreak >nul

echo 🎨 正在啟動 Streamlit 前端...
start cmd /k "streamlit run app.py"