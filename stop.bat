@echo off
chcp 65001 >nul
title 合同归档管理系统 - 关闭中...
cd /d "%~dp0"

echo ============================================
echo   停止合同归档管理系统
echo ============================================
echo.

:: ============================================================
::  策略1：按端口杀（最可靠，不依赖窗口标题）
:: ============================================================
echo [1/3] 终止8000端口进程...
set KILLED=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   - 终止 PID: %%a
    taskkill /PID %%a /F 2>nul
    set KILLED=1
)

if %KILLED%==0 (
    echo   - 8000端口无监听进程
)

:: ============================================================
::  策略2：按窗口标题杀（兜底）
:: ============================================================
echo.
echo [2/3] 清理残留窗口...
taskkill /FI "WINDOWTITLE eq 合同归档-后端*" /F 2>nul
taskkill /FI "WINDOWTITLE eq uvicorn*" /F 2>nul

:: ============================================================
::  策略3：确认端口已释放
:: ============================================================
echo.
echo [3/3] 确认端口已释放...
set /a CHECK=0
:verify_port
timeout /t 1 /nobreak >nul
set /a CHECK+=1
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    if %CHECK% LSS 5 (
        echo   - 端口仍被占用，重试... (%CHECK%/5)
        for /f "tokens=5" %%b in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
            taskkill /F /PID %%b 2>nul
        )
        goto verify_port
    ) else (
        echo   [警告] 端口无法释放，请手动处理
    )
) else (
    echo   - 8000端口已释放
)

echo.
echo ============================================
echo   服务已停止
echo ============================================
echo.
pause
