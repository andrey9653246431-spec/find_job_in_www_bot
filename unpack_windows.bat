@echo off
chcp 65001 >nul
echo ============================================================
echo   Распаковщик и настройка проекта find_job_in_www_bot
echo   Репозиторий: https://github.com/andrey9653246431-spec/find_job_in_www_bot
echo ============================================================

set TARGET_DIR=find_job_in_www_bot

if exist find_job_in_www_bot.zip (
    echo [1/4] Распаковка архива find_job_in_www_bot.zip в папку %TARGET_DIR%...
    powershell -NoProfile -Command "Expand-Archive -Path 'find_job_in_www_bot.zip' -DestinationPath '%TARGET_DIR%' -Force"
) else (
    echo [!] Файл find_job_in_www_bot.zip не найден рядом со скриптом.
    echo     Запускаю самораспаковывающийся Python-скрипт unpack_and_setup.py...
    python unpack_and_setup.py
    pause
    exit /b 0
)

cd /d "%TARGET_DIR%"

if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [2/4] Создан файл .env из шаблона .env.example
    )
)

echo [3/4] Инициализация Git и привязка к репозиторию GitHub...
git init -b main
git add .
git commit -m "feat: initial implementation of find_job_in_www_bot"
git remote remove origin >nul 2>&1
git remote add origin https://github.com/andrey9653246431-spec/find_job_in_www_bot.git

echo [4/4] Готово! Проект распакован в папку: %CD%
echo.
echo Чтобы отправить проект на GitHub, выполните:
echo   cd %TARGET_DIR%
echo   git push -u origin main
echo.
echo Чтобы запустить бота:
echo   1. Укажите BOT_TOKEN в файле %TARGET_DIR%\.env
echo   2. pip install -r requirements.txt
echo   3. python main.py
echo ============================================================
pause
