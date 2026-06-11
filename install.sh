#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  Hermonoid — Web Chat UI for Hermes Agent
#  One-Click Installer
#  https://github.com/Fil-m/hermonoid
# ============================================================
set -e

# Визначаємо версію скрипта
VERSION="1.2.0"

GREEN='\033[1;32m'
BLUE='\033[1;34m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     🤖 Hermonoid — Web Chat for Hermes Agent    ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║        One-Click Installer for Termux            ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================
# Крок 1: Оновлення пакетів
# ============================================================
echo -e "${YELLOW}[1/7] Оновлення пакетів Termux...${NC}"
pkg update -y -o Dpkg::Options::="--force-confnew" 2>&1 | tail -1
pkg upgrade -y -o Dpkg::Options::="--force-confnew" 2>&1 | tail -1

# ============================================================
# Крок 2: Встановлення залежностей
# ============================================================
echo -e "${YELLOW}[2/7] Встановлення необхідних пакетів...${NC}"
pkg install -y python git curl termux-am ripgrep 2>&1 | tail -3

# ============================================================
# Крок 3: Доступ до файлової системи (Android Storage)
# ============================================================
echo -e "${YELLOW}[3/7] Налаштування доступу до файлової системи...${NC}"
STORAGE_FILE="$HOME/.termux/termux.properties"
mkdir -p "$HOME/.termux"

# Дозвіл доступу до зовнішнього сховища
if [ -f "$STORAGE_FILE" ]; then
    if ! grep -q "allow-external-apps" "$STORAGE_FILE" 2>/dev/null; then
        echo "allow-external-apps = true" >> "$STORAGE_FILE"
    fi
else
    echo "allow-external-apps = true" > "$STORAGE_FILE"
fi

# Запит дозволу на сховище (якщо termux-setup-storage доступний)
if command -v termux-setup-storage &>/dev/null; then
    echo -e "${BLUE}  → Запит доступу до сховища Android...${NC}"
    termux-setup-storage 2>/dev/null || true
fi

# ============================================================
# Крок 4: Клонування або оновлення Hermonoid
# ============================================================
echo -e "${YELLOW}[4/7] Встановлення Hermonoid...${NC}"
if [ -d "$HOME/hermonoid/.git" ]; then
    echo -e "${BLUE}  → Оновлення існуючого Hermonoid...${NC}"
    cd "$HOME/hermonoid"
    git pull origin main 2>&1 | tail -2
else
    echo -e "${BLUE}  → Клонування Hermonoid...${NC}"
    git clone https://github.com/Fil-m/hermonoid.git "$HOME/hermonoid" 2>&1 | tail -2
fi

cd "$HOME/hermonoid"

# ============================================================
# Крок 4.5: Створення скриптів для Termux:Widget
# ============================================================
echo -e "${YELLOW}[4.5/7] Створення віджетів для робочого столу...${NC}"
mkdir -p "$HOME/.shortcuts"

cat > "$HOME/.shortcuts/hermonoid.sh" << 'WIDGET'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/hermonoid
pkill -f "server.py" 2>/dev/null || true
sleep 1
nohup python3 server/server.py > /tmp/hermonoid.log 2>&1 &
for i in 1 2 3 4 5; do
    sleep 1
    if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
        break
    fi
done
termux-open-url "http://localhost:8080"
WIDGET
chmod +x "$HOME/.shortcuts/hermonoid.sh"
echo -e "  ${GREEN}✓${NC} Скрипт hermonoid.sh створено"

cat > "$HOME/.shortcuts/terminal.sh" << 'WIDGET2'
#!/data/data/com.termux/files/usr/bin/bash
exec bash
WIDGET2
chmod +x "$HOME/.shortcuts/terminal.sh"
echo -e "  ${GREEN}✓${NC} Скрипт terminal.sh створено"

# ============================================================
# Крок 5: Встановлення Termux:Widget (віджет на робочий стіл)
# ============================================================
echo -e "${YELLOW}[5/7] Встановлення Termux:Widget...${NC}"

# Завантажуємо APK
WIDGET_APK="$HOME/storage/downloads/termux-widget.apk"
if [ ! -f "$WIDGET_APK" ]; then
    WIDGET_URL="https://github.com/termux/termux-widget/releases/download/v0.15.0/termux-widget-app_v0.15.0%2Bgithub.debug.apk"
    echo -e "${BLUE}  → Завантаження Termux:Widget APK...${NC}"
    curl -sL -o "$WIDGET_APK" "$WIDGET_URL" 2>&1 | tail -1
    echo -e "  ${GREEN}✓${NC} APK завантажено: ~/storage/downloads/termux-widget.apk"
else
    echo -e "  ${GREEN}✓${NC} APK вже є: ~/storage/downloads/termux-widget.apk"
fi

# ============================================================
# Крок 6: Перевірка Hermes Agent
# ============================================================
echo -e "${YELLOW}[6/7] Перевірка Hermes Agent...${NC}"
HERMES_BIN="$HOME/.hermes/hermes-agent/venv/bin/hermes"
if [ ! -f "$HERMES_BIN" ]; then
    echo -e "${BLUE}  → Hermes Agent не знайдено. Встановлення...${NC}"
    pip install hermes-agent 2>&1 | tail -3
fi

# ============================================================
# Крок 7: Запуск сервера + копіювання посилання
# ============================================================
echo -e "${YELLOW}[7/7] Запуск Hermonoid сервера...${NC}"

# Вбиваємо старий сервер якщо є
pkill -f "server/server.py" 2>/dev/null || true
sleep 1

# Запускаємо новий
nohup python3 server/server.py > /tmp/hermonoid.log 2>&1 &
sleep 3

# Отримуємо локальну IP
IP_ADDR=$(ifconfig 2>/dev/null | grep -oP 'inet \d+\.\d+\.\d+\.\d+' | grep -v '127.0.0.1' | head -1 | awk '{print $2}')
IP_ADDR="${IP_ADDR:-127.0.0.1}"

# Формуємо посилання
LOCAL_URL="http://localhost:8080"
NET_URL="http://${IP_ADDR}:8080"

# Копіюємо в буфер обміну (якщо termux-clipboard-set доступний)
if command -v termux-clipboard-set &>/dev/null; then
    echo -n "$LOCAL_URL" | termux-clipboard-set
    CLIP_MSG="✓ Скопійовано в буфер обміну!"
else
    CLIP_MSG="(termux-clipboard-set недоступний — скопіюй вручну)"
fi

# Додаємо alias-и в .bashrc
ALIASES=$(cat << 'ALIAS'
# ====== HERMONOID ======
alias hermonoid='cd ~/hermonoid && python3 server/server.py'
alias hchat='cd ~/hermonoid && python3 server/server.py'
alias hurl='bash ~/hermonoid/scripts/hurl.sh'
alias hshortcut='bash ~/hermonoid/scripts/hshortcut.sh'
alias hstart='bash ~/hermonoid/start.sh'
alias hstop='pkill -f "server.py" 2>/dev/null; echo "🛑 Сервер зупинено"'
alias hstatus='pgrep -af server.py | grep -v bash || echo "⚫ Сервер не запущений"'
alias hlog='tail -f ~/hermonoid/server.log'
alias hupdate='cd ~/hermonoid && git pull && echo "🔄 Оновлено"'
alias hsetup='python3 ~/hermonoid/scripts/hermonoid.py'
ALIAS
)
if ! grep -q "HERMONOID" ~/.bashrc 2>/dev/null; then
    echo "$ALIASES" >> ~/.bashrc
    echo -e "${GREEN}  → alias додано в ~/.bashrc${NC}"
fi

# ============================================================
# Фінальний вивід
# ============================================================
clear
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     ✅ Hermonoid встановлено та запущено!        ║"
echo "╠══════════════════════════════════════════════════╣"
echo -e "║${NC}"
echo "║  ${CYAN}Відкрий у браузері:${NC}"
echo -e "║  ${GREEN}${LOCAL_URL}${NC}  $CLIP_MSG"
echo -e "║"
echo -e "║  ${YELLOW}Або просто напиши:${NC} ${GREEN}hurl${NC}"
echo -e "║  ${YELLOW}Або натисни на віджет:${NC} ${GREEN}Hermonoid на столі${NC}"
echo -e "║"
echo -e "║  ${BLUE}🏠 Додати віджет на робочий стіл:${NC}"
echo -e "║  1. Встанови Termux:Widget (APK в Downloads)"
echo -e "║  2. Затисни на столі → Віджети → Termux:Widget"
echo -e "║  3. Обери скрипт: ${CYAN}hermonoid.sh${NC}"
echo -e "║"
echo -e "║  Або через мережу (з іншого пристрою):${NC}"
echo -e "║  ${BLUE}${NET_URL}${NC}"
echo -e "║${NC}"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Подальші кроки:                                ║"
echo "║  1. Налаштуй підключення до моделі               ║"
echo "║  2. Обери або створи нову сесію                  ║"
echo "║  3. Починай спілкування з Hermes Agent!          ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  📖 Документація: github.com/Fil-m/hermonoid     ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
