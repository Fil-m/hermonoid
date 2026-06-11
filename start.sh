#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Hermonoid — запуск веб-чату для Hermes Agent на Android
#  Використовувати: bash start.sh
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
NC='\033[0m'

PORT=8080

# ── Перевірка чи сервер вже запущено ─────────────────
if curl -s http://localhost:${PORT}/api/status > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Сервер Hermonoid вже запущено на http://localhost:${PORT}"
else
    # Запуск сервера в фоновому режимі
    echo -e "${YELLOW}⟳${NC} Запускаю сервер Hermonoid..."
    pkill -f "server.py" 2>/dev/null || true
    sleep 1
    nohup python3 server/server.py > "$DIR/server.log" 2>&1 &
    PID=$!
    
    # Чекаємо готовності
    for i in 1 2 3 4 5; do
        sleep 1
        if curl -s http://localhost:${PORT}/api/status > /dev/null 2>&1; then
            break
        fi
    done
fi

# ── Автовідкриття в браузері Android ─────────────────
if curl -s http://localhost:${PORT}/api/status > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Hermonoid готовий! Відкриваю браузер..."
    
    if command -v termux-open-url &>/dev/null; then
        termux-open-url "http://localhost:${PORT}"
    elif command -v am &>/dev/null; then
        am start -a android.intent.action.VIEW -d "http://localhost:${PORT}" 2>/dev/null
    fi
    
    echo -e "  ${CYAN}http://localhost:${PORT}${NC}"
    echo -e "  🛑 Зупинити: ${YELLOW}hstop${NC}"
else
    echo -e "${YELLOW}✗${NC} Помилка запуску сервера"
    python3 server/server.py
fi
