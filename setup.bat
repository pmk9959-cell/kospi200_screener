@echo off
chcp 65001 >nul
echo.
echo ===============================================================
echo   KOSPI 200 Screener - 의존성 설치 (최초 1회만)
echo ===============================================================
echo.

REM Python 설치 확인
py --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo.
    echo 다음 페이지에서 Python을 먼저 설치해주세요:
    echo    https://www.python.org/downloads/
    echo.
    echo *** 설치 시 "Add Python to PATH" 체크박스를 반드시 켜주세요 ***
    echo.
    pause
    exit /b 1
)

echo [1/2] Python 버전 확인:
py --version
echo.

echo [2/2] 라이브러리 설치 중... (1~3분 소요)
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

echo.
if errorlevel 1 (
    echo ===============================================================
    echo   설치 실패. 위 빨간 글씨 메시지를 확인해주세요.
    echo ===============================================================
) else (
    echo ===============================================================
    echo   ✅ 설치 완료! 이제 run_test.bat 를 더블클릭하세요.
    echo ===============================================================
)
echo.
pause
