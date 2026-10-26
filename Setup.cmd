@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Install Python 3.10 or newer from python.org, including Tcl/Tk and pip.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import tkinter, yt_dlp, imageio_ffmpeg; print('FFmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 goto failed
where node >nul 2>nul
if errorlevel 1 (
    where deno >nul 2>nul
    if errorlevel 1 echo Install Node.js 22 or newer from https://nodejs.org or Deno from https://deno.com before downloading.
)
echo Setup complete. Double-click Start YT Tool.cmd to open the app.
pause
exit /b 0
:failed
echo Setup failed. Review the error above and try again.
pause
exit /b 1
