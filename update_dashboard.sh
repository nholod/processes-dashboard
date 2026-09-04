#!/bin/bash
# Сбор живых cron-данных OpenClaw и публикация дашборда на GitHub Pages.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 "$SCRIPT_DIR/generate_dashboard.py"

git add data/processes.json generate_dashboard.py index.html update_dashboard.sh
if git diff --cached --quiet; then
  echo "OK: данные не изменились"
  exit 0
fi

MSG="${1:-Автообновление данных $(date +%d.%m.%Y)}"
git -c user.name="nholod" -c user.email="nholod@gmail.com" commit -m "$MSG"
git push origin main

echo "OK: дашборд обновлён — https://nholod.github.io/processes-dashboard/"
