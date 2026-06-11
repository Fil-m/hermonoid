#!/data/data/com.termux/files/home/.venv/bin/python
#!/bin/bash
# Hermonoid — встановлення за одну команду
# Використання: curl -fsSL https://raw.githubusercontent.com/Fil-m/hermonoid/main/scripts/install.sh | bash

set -e

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
RED='\033[1;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

echo -e "\n${CYAN}╔════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}HERMONOID${NC} ${DIM}— встановлення${NC}            ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════╝${NC}\n"

# Перевірка Termux
if [ -d "/data/data/com.termux" ]; then
    echo -e "  ${GREEN}✓${NC} Termux виявлено"
else
    echo -e "  ${YELLOW}⚠${NC} Не Termux — деякі функції можуть не працювати"
fi

# Перевірка залежностей
echo -e "\n  ${BOLD}Перевірка залежностей...${NC}"

for cmd in python3 git curl; do
    if command -v $cmd &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $cmd встановлено"
    else
        echo -e "  ${YELLOW}⚠${NC} $cmd не знайдено — встановлюю..."
        pkg install -y $cmd >/dev/null 2>&1
        echo -e "  ${GREEN}✓${NC} $cmd встановлено"
    fi
done

# Клонування
echo -e "\n  ${BOLD}Завантаження Hermonoid...${NC}"
if [ -d "$HOME/hermonoid" ]; then
    echo -e "  ${YELLOW}⚠${NC} ~/hermonoid вже існує"
    read -p "  Оновити? (Y/n): " UPDATE
    if [ "$UPDATE" != "n" ] && [ "$UPDATE" != "N" ]; then
        cd ~/hermonoid && git pull && echo -e "  ${GREEN}✓${NC} Оновлено"
    fi
else
    git clone https://github.com/Fil-m/hermonoid.git ~/hermonoid
    echo -e "  ${GREEN}✓${NC} Завантажено"
fi

# Запуск інсталятора
echo -e "\n  ${BOLD}Запуск інсталятора...${NC}"
cd ~/hermonoid
python3 scripts/hermonoid.py

echo -e "\n${GREEN}  ✓ Встановлення завершено!${NC}"
echo -e "  ${DIM}Відкрий http://localhost:8080 в браузері${NC}\n"
