@echo off
chcp 65001 >nul
title HPoker Texas Hold'em Online 启动管理器

echo ======================================================================
echo   ♠ ♥ ♣ ♦   HPoker 风格多人在线德州扑克系统 (Windows 启动)   ♦ ♣ ♥ ♠  
echo ======================================================================

set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [!] 未检测到 Python 虚拟环境，正在创建 .venv ...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r backend\requirements.txt
)

REM 检查前端依赖
if not exist "frontend\node_modules" (
    echo [!] 未检测到前端依赖，正在执行 npm install ...
    cd frontend
    call npm install
    cd ..
)

echo [✓] 正在同时启动后端与前端服务...
echo.
echo 🌐 本地访问地址: http://localhost:5173
echo 🔌 后端 API 地址: http://localhost:8000
echo 📖 API 接口文档: http://localhost:8000/docs
echo.
echo 💡 提示: 关闭弹出的服务窗口即可停止服务。
echo ======================================================================

start "HPoker-Backend" cmd /k "cd /d %PROJECT_ROOT% && .venv\Scripts\activate.bat && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
start "HPoker-Frontend" cmd /k "cd /d %PROJECT_ROOT%\frontend && npm run dev"
