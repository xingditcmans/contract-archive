@echo off
chcp 65001 >nul
title 合同归档系统 - 缓存清理工具

echo.
echo ============================================
echo    合同归档系统 — 缓存清理工具
echo ============================================
echo.

echo [1/4] 正在删除 Python 缓存文件...
for /d /r "backend" %%d in (__pycache__) do @if exist "%%d" (
    rd /s /q "%%d" 2>nul
    echo   删除: %%d
)
for /r "backend" %%f in (*.pyc) do @if exist "%%f" (
    del /q "%%f" 2>nul
)
echo   完成: 所有 .pyc 和 __pycache__ 已清理

echo.
echo [2/4] 正在删除前端构建缓存...
if exist "frontend\dist" (
    rd /s /q "frontend\dist"
    echo   删除: frontend\dist
)
if exist "frontend\node_modules\.vite" (
    rd /s /q "frontend\node_modules\.vite"
    echo   删除: frontend\node_modules\.vite
)
echo   完成: 前端缓存已清理

echo.
echo [3/4] 正在删除 Python 编译缓存...
if exist "backend\*.pyc" del /q "backend\*.pyc" 2>nul
echo   完成

echo.
echo [4/4] 重新构建前端...
cd /d "%~dp0frontend"
call npx vite build --mode production 2>&1
echo   完成: 前端已重新构建

cd /d "%~dp0"

echo.
echo ============================================
echo    缓存清理完成！
echo    现在启动系统...
echo ============================================
echo.

call "%~dp0start.bat"
