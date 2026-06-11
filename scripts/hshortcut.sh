#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  🏠 hshortcut — додати Hermonoid на робочий стіл Android
#  Використовувати: bash hshortcut.sh
# ============================================================
set -e

GREEN='\033[1;32m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
NC='\033[0m'

DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  🏠 Ярлик Hermonoid на робочий стіл   ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo

# ── 1. Спосіб A: Termux:Widget ──────────────────────
echo -e "${GREEN}1)${NC} ${BLUE}Termux:Widget${NC} — віджет на робочому столі"

if [ -d "$HOME/.shortcuts" ]; then
    SHORTCUT_DIR="$HOME/.shortcuts"
else
    SHORTCUT_DIR="$HOME/.shortcuts"
    mkdir -p "$SHORTCUT_DIR"
fi

# Створюємо скрипт для віджета
cat > "$SHORTCUT_DIR/Hermonoid" << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
# Hermonoid — запуск для Termux:Widget
cd ~/hermonoid

# Вбиваємо старий сервер
pkill -f "server.py" 2>/dev/null || true
sleep 1

# Запускаємо сервер
nohup python3 server/server.py > /tmp/hermonoid.log 2>&1 &

# Чекаємо
for i in 1 2 3 4 5; do
    sleep 1
    if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
        break
    fi
done

# Відкриваємо браузер
termux-open-url "http://localhost:8080"
SCRIPT

chmod +x "$SHORTCUT_DIR/Hermonoid"
echo -e "  ${GREEN}✓${NC} Скрипт створено: $SHORTCUT_DIR/Hermonoid"
echo -e "  ${YELLOW}ℹ${NC} Встанови Termux:Widget з F-Droid"
echo -e "     → Додай віджет на робочий стіл"
echo -e "     → Обери 'Hermonoid'"
echo

# ── 2. Спосіб B: HTML-закладка ──────────────────────
echo -e "${GREEN}2)${NC} ${BLUE}Закладка на головному екрані${NC}"

URL_FILE="$HOME/storage/downloads/Hermonoid.url"
mkdir -p "$HOME/storage/downloads" 2>/dev/null || true
cat > "$URL_FILE" 2>/dev/null || true << 'EOF'
[InternetShortcut]
URL=http://localhost:8080
EOF

echo -e "  ${GREEN}✓${NC} URL-файл: $URL_FILE"
echo -e "  ${YELLOW}ℹ${NC} Або відкрий в Chrome:"
echo -e "     → Меню (⋯) → Додати на головний екран"
echo -e "     → Назва: Hermonoid"
echo

# ── 3. Спосіб C: alias для швидкого запуску ─────────
echo -e "${GREEN}3)${NC} ${BLUE}Швидкий запуск з Termux${NC}"
echo -e "  Просто напиши: ${CYAN}hurl${NC}"

echo
echo -e "${GREEN}✅ Готово!${NC}"
echo -e "  Віджет створено. Додай його на робочий стіл Android:"
echo -e "  1. Встанови ${CYAN}Termux:Widget${NC} з F-Droid"
echo -e "  2. Вийди на робочий стіл"
echo -e "  3. Довге натискання → Віджети → Termux:Widget"
echo -e "  4. Обери скрипт 'Hermonoid'"
echo
