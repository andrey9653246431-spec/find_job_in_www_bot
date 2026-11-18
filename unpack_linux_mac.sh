#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Распаковщик и настройка проекта find_job_in_www_bot"
echo "  Репозиторий: https://github.com/andrey9653246431-spec/find_job_in_www_bot"
echo "============================================================"

TARGET_DIR="find_job_in_www_bot"

if [ -f "find_job_in_www_bot.zip" ]; then
    echo "[1/4] Распаковка архива find_job_in_www_bot.zip в папку ${TARGET_DIR}..."
    mkdir -p "${TARGET_DIR}"
    if command -v unzip >/dev/null 2>&1; then
        unzip -o "find_job_in_www_bot.zip" -d "${TARGET_DIR}"
    else
        python3 -m zipfile -e "find_job_in_www_bot.zip" "${TARGET_DIR}"
    fi
else
    echo "[!] Архив find_job_in_www_bot.zip не найден рядом со скриптом."
    echo "    Запускаю самораспаковывающийся скрипт unpack_and_setup.py..."
    python3 unpack_and_setup.py
    exit 0
fi

cd "${TARGET_DIR}"

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[2/4] Создан файл .env из шаблона .env.example"
fi

if command -v git >/dev/null 2>&1; then
    echo "[3/4] Инициализация Git и привязка к GitHub репозиторию..."
    git init -b main
    git add .
    git commit -m "feat: initial implementation of find_job_in_www_bot" || true
    git remote remove origin >/dev/null 2>&1 || true
    git remote add origin https://github.com/andrey9653246431-spec/find_job_in_www_bot.git
fi

echo "[4/4] Готово! Проект распакован в: $(pwd)"
echo ""
echo "Для отправки кода в ваш GitHub репозиторий выполните:"
echo "  cd ${TARGET_DIR}"
echo "  git push -u origin main"
echo ""
echo "Для запуска бота:"
echo "  1. Впишите BOT_TOKEN в файл ${TARGET_DIR}/.env"
echo "  2. pip install -r requirements.txt && python3 main.py"
echo "============================================================"
