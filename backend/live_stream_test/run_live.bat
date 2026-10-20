@echo off
setlocal
echo ===================================================
echo   CS472 Mocap - MediaPipe Live Stream Studio
echo ===================================================
echo.

cd /d "%~dp0..\.."

echo [1/2] Verifying Python backend virtualenv...
if not exist "backend\.venv\Scripts\python.exe" (
    echo Error: backend\.venv\Scripts\python.exe not found!
    echo Please set up the backend virtual environment first.
    pause
    exit /b 1
)

backend\.venv\Scripts\python.exe -c "import websockets, cv2, mediapipe" 2>nul
if %errorlevel% neq 0 (
    echo Installing live stream dependencies...
    backend\.venv\Scripts\pip.exe install -r backend\live_stream_test\requirements.txt
)

echo [2/2] Launching Electron Live Studio...
cd desktop
npx.cmd electron ..\backend\live_stream_test\gui

endlocal
