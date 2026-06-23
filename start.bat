@echo off
chcp 65001 >nul
title 合同归档管理系统 - 启动中...
cd /d "%~dp0"

echo ============================================
echo   合同归档管理系统 v1.1
echo ============================================
echo.

:: ============================================================
::  第1步：彻底释放 8000 端口
:: ============================================================
echo [1/5] 释放8000端口...

set PORT_FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   - 终止占用进程 PID: %%a
    taskkill /PID %%a /F 2>nul
    set PORT_FOUND=1
)

if %PORT_FOUND%==0 (
    echo   - 端口空闲，无需释放
) else (
    :: 等待端口真正释放（TIME_WAIT 可能要几秒）
    echo   - 等待端口完全释放...
    :wait_free
    timeout /t 1 /nobreak >nul
    netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo   - 端口仍被占用，强制终止...
        for /f "tokens=5" %%b in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
            taskkill /F /PID %%b 2>nul
        )
        goto wait_free
    )
    echo   - 端口已释放
)

:: ============================================================
::  第2步：清理 Python 缓存
:: ============================================================
echo.
echo [2/5] 清理Python缓存...
for /d /r "backend" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q "backend\*.pyc" 2>nul
echo   - 缓存清理完成

:: ============================================================
::  第3步：验证环境
:: ============================================================
echo.
echo [3/5] 验证运行环境...

if not exist "backend\venv\Scripts\python.exe" (
    echo   [错误] 虚拟环境不存在: backend\venv\Scripts\python.exe
    echo   [提示] 请先创建虚拟环境: cd backend ^&^& python -m venv venv
    pause
    exit /b 1
)
echo   - 虚拟环境: OK

if not exist "backend\app\main.py" (
    echo   [错误] 未找到后端入口: backend\app\main.py
    pause
    exit /b 1
)
echo   - 后端主程序: OK

if not exist "frontend\dist\app.html" (
    echo   [警告] 前端构建产物缺失，正在构建...
    cd /d "%~dp0frontend"
    call npm install --silent 2>nul
    call npx vite build
    cd /d "%~dp0"
    if not exist "frontend\dist\app.html" (
        echo   [错误] 前端构建失败！
        pause
        exit /b 1
    )
    echo   - 前端构建: 完成
) else (
    echo   - 前端构建产物: OK
)

:: ============================================================
::  第4步：启动后端（cmd /k 保证窗口不闪退）
:: ============================================================
echo.
echo [4/5] 启动后端服务...

:: 使用 cmd /k（不是 /c），这样 uvicorn 万一崩了，窗口会留着让你看到报错
start "合同归档-后端" cmd /k "cd /d %~dp0backend && echo ============================================ && echo  合同归档-后端 uvicorn :8000 && echo  关闭本窗口可停止服务 && echo ============================================ && echo. && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: ============================================================
::  第5步：健康检查（轮询直到服务就绪）
:: ============================================================
echo [5/5] 等待服务就绪...

set /a TRY=0
:health_loop
timeout /t 2 /nobreak >nul
set /a TRY+=1

:: 用 curl 做 HTTP 健康探测（比 netstat 更可靠，能确认服务真正可用）
curl -s -o nul -w "%%{http_code}" http://localhost:8000/health 2>nul | findstr "200" >nul 2>&1
if errorlevel 1 (
    if %TRY% LSS 20 (
        echo   - 等待中... %TRY%/20
        goto health_loop
    ) else (
        echo.
        echo ============================================
        echo   [失败] 服务启动超时！
        echo.
        echo   可能原因:
        echo   1. 查看"合同归档-后端"窗口中的红色报错
        echo   2. 端口8000被其他程序占用
        echo   3. Python依赖缺失，运行 pip install
        echo ============================================
        pause
        exit /b 1
    )
)

echo   - 服务就绪！轮询 %TRY% 次后成功

:: ============================================================
::  打开浏览器
:: ============================================================
echo.
echo ============================================
echo   启动成功！
echo   地址: http://localhost:8000
echo   提示: 首次使用请修改默认管理员密码
echo ============================================
echo.
start http://localhost:8000

echo 后端运行在"合同归档-后端"窗口中
echo 要停止服务: ① 关闭该窗口 ② 或双击 stop.bat
echo.
pause
