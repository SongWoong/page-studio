@echo off
chcp 65001 > nul
echo Page Studio 시작 중...
cd /d "%~dp0"

for /f "tokens=1,* delims==" %%a in (.env) do (
    set "%%a=%%b"
)

echo API 키 로드 완료
python app.py
pause
