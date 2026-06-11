# 🤖 Hermonoid

**Web Chat UI for Hermes Agent on Android**

Hermonoid — це веб-інтерфейс для спілкування з Hermes Agent прямо з браузера. Працює на Android через Termux. Жодного root не потрібно.

![Hermonoid](https://img.shields.io/badge/Android-Termux-green)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## ⚡ One-Click Install

Відкрий **Termux** і встав єдину команду:

```bash
bash <(curl -s https://raw.githubusercontent.com/Fil-m/hermonoid/main/install.sh)
```

ℹ️ **Що станеться:**
- Оновлення пакетів Termux
- Встановлення Python, git, curl
- Запит доступу до файлової системи
- Клонування Hermonoid
- 🏠 **Автоматичне створення віджетів** для робочого столу
- 📥 **Завантаження Termux:Widget APK** в Downloads
- Запуск веб-сервера
- Посилання скопіюється в буфер обміну

Після встановлення:

1. Відкрий файловий менеджер → **Downloads** → встанови `termux-widget.apk`
2. На робочому столі: затисни → **Віджети** → **Termux:Widget** → обери `hermonoid.sh`
3. Натисни на віджет — і чат відкриється в браузері!

---

## 🛠 Ручне встановлення

```bash
pkg update && pkg upgrade -y
pkg install -y python git curl
git clone https://github.com/Fil-m/hermonoid.git
cd hermonoid
bash start.sh
```

Відкрий `http://localhost:8080` у браузері.

---

## ⚡ Швидкий запуск (після встановлення)

```bash
hurl         # Запустити сервер + відкрити браузер (автоматично)
hchat        # Запустити веб-чат
hstop        # Зупинити сервер
hstatus      # Статус сервера
hlog         # Лог сервера
hupdate      # Оновити з GitHub
hshortcut    # Додати ярлик на робочий стіл Android
hsetup       # Повторне налаштування
```

> **💡** `hurl` — головна команда. Запускає сервер (якщо не запущено) і відразу відкриває браузер на телефоні через `termux-open-url`.

---

## 🚀 Особливості

- **Веб-чат** — спілкуйся з Hermes Agent через браузер
- **Сесії** — керуй кількома діалогами
- **REST API** — OpenAI-сумісний API для зовнішніх програм
- **Медіа** — завантажуй файли, зображення, голосові повідомлення
- **Термінал** — виконуй команди через веб-інтерфейс
- **Мережа** — доступ з інших пристроїв по Wi-Fi

---

## 📱 Доступ через мережу

Після запуску сервер буде доступний на:

| Адреса | Опис |
|--------|------|
| `http://localhost:8080` | На самому телефоні |
| `http://<IP>:8080` | З інших пристроїв в мережі |

---

## 🔧 Продовження роботи

Якщо вийшов з Termux і хочеш знову запустити:

```bash
bash ~/hermonoid/start.sh
```

Або просто:
```bash
hurl
```

Або додай у `~/.bashrc`:

```bash
echo "bash ~/hermonoid/start.sh" >> ~/.bashrc
```

Тоді Hermonoid стартуватиме автоматично при кожному вході.

---

## 🔧 Troubleshooting

| Проблема | Рішення |
|----------|---------|
| Сервер не запускається | `pkill -f "server.py"` потім `hurl` |
| "Address already in use" | `pkill -f "server.py" && hurl` |
| "Module not found" | `pip install -r ~/hermonoid/requirements.txt` |
| Сторінка не відкривається | Відкрий `http://localhost:8080` вручну |
| Hermes не відповідає | `hermes config` — перевір модель і ключ |
| Інші помилки | `cat /tmp/hermonoid.log` — подивись лог |

Якщо нічого не допомогло — створи Issue на [GitHub](https://github.com/Fil-m/hermonoid/issues).

---

## 📋 Структура проєкту

```
hermonoid/
├── install.sh          # One-click інсталятор
├── start.sh            # Скрипт запуску
├── server/
│   └── server.py       # Веб-сервер + API
├── web/
│   └── index.html      # Веб-клієнт
├── scripts/
│   ├── hermonoid.py    # Додаткові утиліти
│   ├── hurl.sh         # Запуск + автовідкриття браузера
│   └── hshortcut.sh    # Ярлик на робочий стіл Android
└── README.md
```

---

## 📄 Ліцензія

MIT
