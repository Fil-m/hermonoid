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
- Запуск веб-сервера
- Посилання скопіюється в буфер обміну

Після встановлення відкрий браузер → встав посилання → налаштовуй у вебі.

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

Або додай у `~/.bashrc`:

```bash
echo "bash ~/hermonoid/start.sh" >> ~/.bashrc
```

Тоді Hermonoid стартуватиме автоматично при кожному вході.

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
│   └── install.sh      # Legacy інсталятор
└── README.md
```

---

## 📄 Ліцензія

MIT
