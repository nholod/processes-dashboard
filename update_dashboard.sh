#!/bin/bash
# Обновление дашборда процессов на GitHub Pages.
# Использование: ./update_dashboard.sh [commit_message]
set -e
cd /home/alexey/.openclaw/workspace-producer/dashboard

MSG="${1:-Обновление данных дашборда}"

git add -A
git -c user.name="nholod" -c user.email="nholod@gmail.com" commit -m "$MSG" >/dev/null 2>&1 || { echo "Нет изменений для коммита"; }
git push origin main 2>&1 | tail -1

echo "OK: дашборд обновлён — https://nholod.github.io/processes-dashboard/"
