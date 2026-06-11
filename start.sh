#!/data/data/com.termux/files/usr/bin/bash
# Hermonoid — запуск веб-чату для Hermes Agent на Android
# Використовувати: bash start.sh

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Перевірка чи сервер вже запущено
if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "✓ Сервер Hermonoid вже запущено на http://localhost:8080"
    exit 0
fi

# Запуск сервера в фоновому режимі
nohup python3 server/server.py > /dev/null 2>&1 &
PID=$!
sleep 2

if kill -0 $PID 2>/dev/null; then
    echo "✓ Hermonoid запущено! (PID: $PID)"
    echo "  http://localhost:8080"
else
    echo "✗ Помилка запуску сервера"
    python3 server/server.py
fi
