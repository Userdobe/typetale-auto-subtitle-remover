@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist config.json copy /y config.example.json config.json >nul
echo 正在启动字字动画自动去字幕监视器...
python -m venv .venv 2>nul
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python remove_subtitles.py --config config.json
pause
