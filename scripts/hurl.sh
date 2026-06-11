#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  🚀 hurl — Hermonoid URL Opener
#  Запускає сервер + відкриває URL у браузері Android
# ============================================================
set -e

GREEN='\033[1;32m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
NC='\033[0m'

DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT=8080
LOCAL_URL="http://localhost:${PORT}"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  🚀 ${GREEN}Hermonoid${NC} — запуск + відкриття    ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo

# ── 1. Вбиваємо старий сервер якщо висить ──────────
if curl -s "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Сервер вже працює!"
else
    echo -e "${YELLOW}⟳${NC} Запускаю сервер..."
    pkill -f "server.py" 2>/dev/null || true
    sleep 1
    nohup python3 "${DIR}/server/server.py" > /tmp/hermonoid.log 2>&1 &
    PID=$!
    
    # Чекаємо готовності
    for i in 1 2 3 4 5; do
        sleep 1
        if curl -s "http://localhost:${PORT}/api/status" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Сервер запущено! (PID: $PID)"
            break
        fi
        if [ "$i" -eq 5 ]; then
            echo -e "${YELLOW}⚠${NC} Сервер запущено, але статус не підтверджено"
        fi
    done
fi

# ── 2. Відкриваємо в браузері (Android am start) ──
echo
echo -e "${BLUE}⟳${NC} Відкриваю в браузері..."

if command -v termux-open-url &>/dev/null; then
    # Termux: відкриває в стандартному браузері
    termux-open-url "${LOCAL_URL}"
    echo -e "${GREEN}✓${NC} Відкрито через termux-open-url"
elif command -v am &>/dev/null; then
    # Android: через activity manager
    am start -a android.intent.action.VIEW -d "${LOCAL_URL}" 2>/dev/null
    echo -e "${GREEN}✓${NC} Відкрито через am start"
elif command -v xdg-open &>/dev/null; then
    # Linux/Desktop
    xdg-open "${LOCAL_URL}" 2>/dev/null
    echo -e "${GREEN}✓${NC} Відкрито через xdg-open"
else
    echo -e "${YELLOW}⚠${NC} Не можу відкрити браузер автоматично"
    echo -e "  Відкрий вручну: ${CYAN}${LOCAL_URL}${NC}"
fi

# ── 3. Інфо ────────────────────────────────────────
echo
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  📱 ${CYAN}${LOCAL_URL}${NC}           ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  🛑 Зупинити: ${YELLOW}hstop${NC}              ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo
echo -e "  Або запусти вручну: ${CYAN}hchat${NC}"
echo
