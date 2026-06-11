#!/data/data/com.termux/files/home/.venv/bin/python
"""
hermonoid — скрипт для налаштування Hermes Agent на Android
=============================================================

Використання:
  python3 hermonoid.py              # Інтерактивний режим
  python3 hermonoid.py --auto       # Автоматичне налаштування
  python3 hermonoid.py --help       # Довідка

Що робить:
  1. Встановлює/оновлює Hermes Agent (якщо треба)
  2. Налаштовує модель (OpenRouter, DeepSeek, Anthropic тощо)
  3. Вмикає потрібні toolsets (terminal, web, file, skills...)
  4. Створює веб-чат Hermonoid Chat
  5. Налаштовує автозапуск сервера при старті Termux
  6. Встановлює alias `hermonoid` для швидкого доступу
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time

# ========== КОНСТАНТИ ==========

HERMONOID_DIR = os.path.expanduser("~/hermonoid")
HERMES_HOME = os.path.expanduser("~/.hermes")
HERMES_BIN = os.path.join(HERMES_HOME, "hermes-agent", "venv", "bin", "hermes")
VENV_PYTHON = os.path.join(HERMES_HOME, "hermes-agent", "venv", "bin", "python3")
CHAT_PORT = 8080
SCRIPTS_DIR = os.path.join(HERMONOID_DIR, "scripts")
CONFIG_DIR = os.path.join(HERMONOID_DIR, "config")
SERVER_DIR = os.path.join(HERMONOID_DIR, "server")
WEB_DIR = os.path.join(HERMONOID_DIR, "web")

COLORS = True
try:
    import colorama
    colorama.init()
except ImportError:
    COLORS = False

def c(code, text):
    if COLORS:
        return f"\033[{code}m{text}\033[0m"
    return text

GREEN = lambda t: c("1;32", t)
YELLOW = lambda t: c("1;33", t)
RED = lambda t: c("1;31", t)
CYAN = lambda t: c("1;36", t)
BOLD = lambda t: c("1", t)
DIM = lambda t: c("2", t)

HEADER = f"""
{CYAN("╔════════════════════════════════════════════╗")}
{CYAN("║")}  {BOLD("HERMONOID")} — {DIM("Hermes Agent + Android")}      {CYAN("║")}
{CYAN("║")}  {DIM("Налаштування AI-агента на телефоні")}    {CYAN("║")}
{CYAN("╚════════════════════════════════════════════╝")}
"""

PROVIDERS = {
    "1": {"name": "OpenRouter", "key": "OPENROUTER_API_KEY", "model": "anthropic/claude-sonnet-4", "url": "https://openrouter.ai/api/v1"},
    "2": {"name": "DeepSeek", "key": "DEEPSEEK_API_KEY", "model": "deepseek-chat", "url": "https://api.deepseek.com"},
    "3": {"name": "Anthropic (Claude)", "key": "ANTHROPIC_API_KEY", "model": "claude-sonnet-4", "url": ""},
    "4": {"name": "Google Gemini", "key": "GEMINI_API_KEY", "model": "gemini-2.0-flash", "url": ""},
    "5": {"name": "xAI (Grok)", "key": "XAI_API_KEY", "model": "grok-3", "url": ""},
    "6": {"name": "OpenAI", "key": "OPENAI_API_KEY", "model": "gpt-4o", "url": ""},
    "7": {"name": "Локальна модель (llama.cpp)", "key": "", "model": "local", "url": "http://localhost:8080/v1"},
}

TOOLSETS = {
    "terminal": "Shell команди на Android",
    "web": "Пошук в інтернеті",
    "file": "Читання/запис файлів",
    "skills": "Навички AI",
    "memory": "Пам'ять між сесіями",
    "session_search": "Пошук по історії",
    "delegation": "Делегування завдань",
    "cronjob": "Планувальник завдань",
    "vision": "Аналіз зображень",
    "code_execution": "Запуск Python в пісочниці",
}


# ========== УТИЛІТИ ==========

def run(cmd, timeout=60, check=False):
    """Виконати команду"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", -1
    except Exception as e:
        return "", str(e), -1

def ask(question, default=None):
    """Запитати користувача"""
    if default:
        prompt = f"  {question} [{default}]: "
    else:
        prompt = f"  {question}: "
    try:
        answer = input(prompt).strip()
        return answer if answer else (default or "")
    except (EOFError, KeyboardInterrupt):
        return default or ""

def confirm(question, default=True):
    """Так/ні"""
    hint = "Y/n" if default else "y/N"
    answer = ask(f"{question} ({hint})", "y" if default else "n")
    return answer.lower() in ("y", "yes", "")

def print_step(num, text):
    """Крок установки"""
    print(f"\n{YELLOW(f'[{num}/7]')} {BOLD(text)}")

def print_ok(text):
    print(f"  {GREEN('✓')} {text}")

def print_info(text):
    print(f"  {CYAN('ℹ')} {text}")

def print_warn(text):
    print(f"  {YELLOW('⚠')} {text}")

def print_error(text):
    print(f"  {RED('✗')} {text}")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


# ========== ОСНОВНІ ФУНКЦІЇ ==========

def check_environment():
    """Перевірка оточення"""
    print_step(1, "Перевірка оточення")

    # Android / Termux?
    is_termux = "com.termux" in os.environ.get("PREFIX", "")
    is_android = is_termux or os.path.exists("/system/bin/adb")

    if is_termux:
        print_ok(f"Termux на Android {run('getprop ro.build.version.release')[0]}")
    elif is_android:
        print_info("Android виявлено")
    else:
        print_warn("Не Android — деякі функції можуть не працювати")

    # Python
    py_ver = sys.version.split()[0]
    print_ok(f"Python {py_ver}")

    # Git
    _, _, rc = run("git --version")
    if rc == 0:
        print_ok("Git встановлено")
    else:
        print_warn("Git не знайдено — інсталяція...")
        run("pkg install -y git", timeout=120)
        _, _, rc = run("git --version")
        if rc == 0:
            print_ok("Git встановлено")
        else:
            print_error("Не вдалося встановити Git")

    return is_termux


def check_hermes():
    """Перевірка Hermes Agent"""
    hermes_found = os.path.exists(HERMES_BIN)
    if hermes_found:
        ver, _, _ = run(f"{HERMES_BIN} --version")
        print_ok(f"Hermes Agent {ver or 'встановлено'}")
        return True
    else:
        print_info("Hermes Agent не знайдено")
        return False


def install_or_update_hermes():
    """Встановлення або оновлення Hermes"""
    print_step(2, "Встановлення Hermes Agent")

    if check_hermes():
        if confirm("Hermes вже встановлено. Оновити?"):
            print_info("Завантаження оновлення...")
            out, err, rc = run("curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash", timeout=300)
            if rc == 0:
                print_ok("Hermes оновлено")
            else:
                print_error(f"Помилка оновлення: {err[:200]}")
        else:
            print_ok("Використовуємо існуючу версію")
        return

    if not confirm("Hermes не знайдено. Встановити?"):
        print_warn("Пропускаємо встановлення Hermes")
        return

    print_info("Завантаження Hermes Agent...")
    out, err, rc = run("curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash", timeout=300)

    if rc == 0:
        print_ok("Hermes Agent встановлено!")
        # Оновлюємо шлях
        global HERMES_BIN
        HERMES_BIN = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")
    else:
        print_error(f"Помилка: {err[:300]}")
        print_info("Спробуй вручну: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash")


def configure_model():
    """Налаштування моделі"""
    print_step(3, "Налаштування моделі AI")

    print(f"\n  {BOLD('Оберіть провайдера:')}\n")

    for key, p in PROVIDERS.items():
        has_key = p["key"] and os.environ.get(p["key"])
        icon = GREEN("✓") if has_key else DIM(" ")
        print(f"  {key}. {icon} {p['name']} — {DIM(p['model'])}")

    print(f"  8. {DIM('Пропустити (налаштую пізніше)')}")
    print()

    choice = ask("Вибір", "8")

    if choice == "8" or not choice:
        print_info("Налаштування моделі пропущено")
        return

    provider = PROVIDERS.get(choice)
    if not provider:
        print_error("Невірний вибір")
        return

    # Ключ API
    key_name = provider["key"]
    current_key = os.environ.get(key_name, "")

    if key_name:
        api_key = ask(f"Введіть API ключ для {provider['name']}",
                      "********" if current_key else "")
        if api_key and api_key != "********":
            try:
                # Додаємо в .env Hermes
                env_path = os.path.join(HERMES_HOME, ".env")
                existing = {}
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if "=" in line:
                                k, v = line.strip().split("=", 1)
                                existing[k] = v

                existing[key_name] = api_key

                with open(env_path, "w") as f:
                    for k, v in existing.items():
                        f.write(f"{k}={v}\n")

                os.environ[key_name] = api_key
                print_ok(f"Ключ {key_name} збережено в ~/.hermes/.env")
            except Exception as e:
                print_error(f"Помилка: {e}")

    # Модель
    if confirm(f"Встановити модель {provider['model']}?"):
        cmd = f"{HERMES_BIN} config set model.default {provider['model']}"
        if provider.get("url"):
            cmd += f" && {HERMES_BIN} config set model.base_url {provider['url']}"
        run(cmd)
        # Встановлюємо провайдера
        provider_name = provider["name"].lower().split()[0]
        run(f"{HERMES_BIN} config set model.provider {provider_name}")
        print_ok(f"Модель: {provider['model']}, провайдер: {provider_name}")

    print_ok(f"Модель {provider['name']} налаштована!")


def configure_tools():
    """Налаштування інструментів"""
    print_step(4, "Налаштування інструментів")

    print(f"\n  {BOLD('Які інструменти Hermes увімкнути?')}\n")

    enabled_tools = []
    for tool, desc in TOOLSETS.items():
        if confirm(f"  {tool} — {DIM(desc)}", default=(tool in ("terminal", "file", "web", "skills"))):
            enabled_tools.append(tool)

    if enabled_tools:
        for tool in enabled_tools:
            run(f"{HERMES_BIN} tools enable {tool}")
        print_ok(f"Увімкнено: {', '.join(enabled_tools)}")
    else:
        print_warn("Жодного інструменту не вибрано")


def setup_chat_server():
    """Налаштування веб-чату"""
    print_step(5, "Налаштування Hermonoid Chat Server")

    print_info("Створення файлів сервера...")

    # Копіюємо файли, якщо їх нема
    files_ok = os.path.exists(os.path.join(SERVER_DIR, "server.py")) and \
               os.path.exists(os.path.join(WEB_DIR, "index.html"))

    if not files_ok:
        print_info("Файли проекту не знайдено. Створюю...")

        # Тут мають бути файли з проекту — скопіюємо з hermes_chat
        src_server = os.path.expanduser("~/hermes_chat/server.py")
        src_web = os.path.expanduser("~/hermes_chat/index.html")

        if os.path.exists(src_server):
            shutil.copy2(src_server, os.path.join(SERVER_DIR, "server.py"))
        if os.path.exists(src_web):
            shutil.copy2(src_web, os.path.join(WEB_DIR, "index.html"))

    # Порт
    global CHAT_PORT
    port_input = ask("Порт веб-сервера", str(CHAT_PORT))
    CHAT_PORT = int(port_input) if port_input.isdigit() else CHAT_PORT

    # Оновити порт в server.py
    server_py = os.path.join(SERVER_DIR, "server.py")
    if os.path.exists(server_py):
        with open(server_py) as f:
            content = f.read()
        content = content.replace("PORT = 8080", f"PORT = {CHAT_PORT}")
        with open(server_py, "w") as f:
            f.write(content)

    print_ok(f"Сервер буде на порту {CHAT_PORT}")

    # Автозапуск
    if confirm("Додати автозапуск сервера при старті Termux?"):
        bashrc_path = os.path.expanduser("~/.bashrc")
        start_cmd = f"~/hermonoid/start-chat.sh"

        # Створюємо скрипт запуску
        with open(os.path.join(SCRIPTS_DIR, "start-chat.sh"), "w") as f:
            f.write(f"""#!/data/data/com.termux/files/home/.venv/bin/python
import os, subprocess, sys

def is_running():
    try:
        r = subprocess.run(["pgrep", "-f", "server.py"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except: return False

if __name__ == "__main__":
    if not is_running():
        server_path = os.path.expanduser("~/hermonoid/server/server.py")
        log_path = os.path.expanduser("~/hermonoid/server.log")
        with open(log_path, "a") as log:
            subprocess.Popen(
                [sys.executable, server_path],
                stdout=log, stderr=log,
                cwd=os.path.expanduser("~/hermonoid"),
                env={{**os.environ, "TERM": "xterm-256color"}}
            )
        print("🚀 Hermonoid Chat Server запущено на порту {CHAT_PORT}")
""")
        # Робимо виконуваним
        os.chmod(os.path.join(SCRIPTS_DIR, "start-chat.sh"), 0o755)

        # Додаємо в .bashrc
        bashrc_add = f'\n# Hermonoid Chat Server\ntest -f ~/hermonoid/scripts/start-chat.sh && ~/hermonoid/scripts/start-chat.sh\n'

        if os.path.exists(bashrc_path):
            with open(bashrc_path) as f:
                content = f.read()
            if "hermonoid" not in content:
                with open(bashrc_path, "a") as f:
                    f.write(bashrc_add)
        else:
            with open(bashrc_path, "w") as f:
                f.write(bashrc_add)

        print_ok("Автозапуск додано в ~/.bashrc")

    print_ok("Hermonoid Chat Server налаштовано!")


def create_aliases():
    """Створення alias-ів"""
    print_step(6, "Створення команд Termux")

    aliases = f"""
# ====== HERMONOID ======
alias hermonoid='cd ~/hermonoid && python3 server.py'
alias hchat='cd ~/hermonoid && python3 server.py'
alias hstart='~/hermonoid/scripts/start-chat.sh'
alias hstop='pkill -f "server.py" 2>/dev/null; echo "Сервер зупинено"'
alias hstatus='pgrep -af server.py | grep -v bash || echo "Сервер не запущений"'
alias hlog='tail -f ~/hermonoid/server.log'
alias hupdate='cd ~/hermonoid && git pull && echo "Оновлено"'
alias hsetup='python3 ~/hermonoid/scripts/hermonoid.py'
"""

    bashrc_path = os.path.expanduser("~/.bashrc")
    with open(bashrc_path, "a") as f:
        f.write(aliases)

    print_ok(f"Alias створено:")
    print(f"  {GREEN('hermonoid')}  — запустити веб-чат")
    print(f"  {GREEN('hchat')}     — те саме")
    print(f"  {GREEN('hstart')}   — запустити в фоні")
    print(f"  {GREEN('hstop')}    — зупинити сервер")
    print(f"  {GREEN('hstatus')}  — статус сервера")
    print(f"  {GREEN('hlog')}     — лог сервера")
    print(f"  {GREEN('hupdate')}  — оновити з GitHub")
    print(f"  {GREEN('hsetup')}   — повторне налаштування")


def run_chat_server():
    """Запуск сервера"""
    print_step(7, "Запуск сервера")

    ip = get_local_ip()
    print(f"\n  {BOLD('Hermonoid Chat Server готовий до запуску!')}\n")
    print(f"  📱 {CYAN('http://localhost:' + str(CHAT_PORT))}")
    print(f"  📡 {CYAN('http://' + ip + ':' + str(CHAT_PORT))}")
    print()

    if confirm("Запустити сервер зараз?"):
        out, err, rc = run(
            f"cd ~/hermonoid && {sys.executable} server/server.py &",
            timeout=3
        )
        time.sleep(2)

        # Перевіряємо
        import urllib.request
        try:
            resp = urllib.request.urlopen(f"http://localhost:{CHAT_PORT}/api/status")
            data = json.loads(resp.read())
            if data.get("status") == "ok":
                print_ok(f"Сервер працює на http://localhost:{CHAT_PORT}")
                print_info(f"Відкрий в браузері на телефоні або зайди з комп'ютера")
            else:
                print_warn("Сервер запущено, але статус не підтверджено")
        except Exception as e:
            print_warn(f"Сервер запущено. Перевір: http://localhost:{CHAT_PORT}")
    else:
        print_info("Сервер не запущено. Скористайся командою: hermonoid")

    return ip


def final_message(ip):
    """Фінальне повідомлення"""
    print()
    print(CYAN("╔════════════════════════════════════════════╗"))
    print(CYAN("║") + f"  {BOLD('🎉 Hermonoid налаштовано!')}          {CYAN('║')}")
    print(CYAN("╠════════════════════════════════════════════╣"))
    print(CYAN("║") + f"  📱 Веб-чат: {CYAN(f'http://localhost:{CHAT_PORT}')}        {CYAN('║')}")
    print(CYAN("║") + f"  📡 Мережа:  {CYAN(f'http://{ip}:{CHAT_PORT}')}        {CYAN('║')}")
    print(CYAN("║") + f"  🔧 Команди: {GREEN('hermonoid')}, {GREEN('hchat')}, {GREEN('hstop')}      {CYAN('║')}")
    print(CYAN("║") + f"  📋 Налаштуй знову: {GREEN('hsetup')}      {CYAN('║')}")
    print(CYAN("╚════════════════════════════════════════════╝"))
    print()

    if confirm("Бажаєш зберегти налаштування як скіл для Hermes?"):
        save_skill()

    print(f"\n{GREEN('Дякую! Hermonoid чекає на http://localhost:' + str(CHAT_PORT))}")


def save_skill():
    """Зберегти скіл для Hermes"""
    skill_content = f"""---
name: hermonoid
description: "Hermonoid — Hermes Agent + Android веб-чат. Налаштування та запуск."
version: 1.0.0
author: Fil-m
platforms: [android, linux]
---

# Hermonoid

Hermonoid — це веб-інтерфейс для Hermes Agent, оптимізований для Android/Termux.

## Швидкий старт

```bash
# Запустити сервер
hermonoid

# Або через alias
hchat

# Статус
hstatus

# Зупинити
hstop

# Логи
hlog

# Оновити з GitHub
hupdate

# Налаштувати заново
hsetup
```

## Структура

```
~/hermonoid/
├── server/server.py    # HTTP сервер + API
├── web/index.html      # Веб-інтерфейс чату
├── scripts/
│   ├── hermonoid.py    # Інсталятор (цей скрипт)
│   └── start-chat.sh   # Автозапуск
├── config/             # Конфігурація
└── README.md
```

## API

| Метод | Шлях | Опис |
|-------|------|------|
| GET | /api/status | Статус сервера |
| GET | /api/sessions | Список сесій |
| POST | /api/sessions | Створити сесію |
| GET | /api/sessions/:id | Сесія + повідомлення |
| POST | /api/sessions/:id/rename | Перейменувати |
| DELETE | /api/sessions/:id | Видалити сесію |
| POST | /api/chat | Надіслати повідомлення |
| POST | /api/exec | Виконати команду |

## Порти

За замовчуванням: 8080. Можна змінити при налаштуванні.
"""
    skill_path = os.path.join(HERMES_HOME, "skills", "hermonoid", "SKILL.md")
    os.makedirs(os.path.dirname(skill_path), exist_ok=True)
    with open(skill_path, "w") as f:
        f.write(skill_content)
    print_ok("Скіл 'hermonoid' збережено для Hermes!")


# ========== НЕІНТЕРАКТИВНИЙ РЕЖИМ ==========

def auto_setup():
    """Автоматичне налаштування без запитань"""
    print(HEADER)
    print(f"  {DIM('Автоматичний режим...')}\n")

    check_environment()
    install_or_update_hermes()

    # Вмикаємо базові інструменти
    for tool in ["terminal", "file", "web", "skills", "memory", "session_search"]:
        run(f"{HERMES_BIN} tools enable {tool}")

    setup_chat_server()

    # Створюємо alias
    bashrc_path = os.path.expanduser("~/.bashrc")
    with open(bashrc_path, "a") as f:
        f.write(f"""
# ====== HERMONOID ======
alias hermonoid='cd ~/hermonoid && python3 server/server.py'
alias hchat='cd ~/hermonoid && python3 server/server.py'
alias hstart='~/hermonoid/scripts/start-chat.sh'
alias hstop='pkill -f "server.py" 2>/dev/null; echo "Сервер зупинено"'
alias hstatus='pgrep -af server.py | grep -v bash || echo "Сервер не запущений"'
alias hupdate='cd ~/hermonoid && git pull && echo "Оновлено"'
alias hsetup='python3 ~/hermonoid/scripts/hermonoid.py'
""")

    print_ok("Hermonoid налаштовано в автоматичному режимі!")
    print_info(f"Відкрий http://localhost:{CHAT_PORT}")


# ========== ГОЛОВНА ==========

def main():
    print(HEADER)

    if "--auto" in sys.argv:
        auto_setup()
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    is_termux = check_environment()
    has_hermes = check_hermes()

    if not has_hermes:
        install_or_update_hermes()

    configure_model()
    configure_tools()
    setup_chat_server()
    create_aliases()
    ip = run_chat_server()
    final_message(ip)


if __name__ == "__main__":
    main()
