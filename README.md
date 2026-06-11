# 🤖 Hermonoid

**Hermes Agent + Android = Hermonoid**

Hermonoid — це веб-інтерфейс для [Hermes Agent](https://hermes-agent.nousresearch.com) від Nous Research, оптимізований для роботи на Android через Termux. Чат з AI-агентом прямо в браузері, на твоєму телефоні, без необхідності ПК.

## 🚀 Можливості

- 💬 **Веб-чат** з Hermes Agent — спілкуйся з AI прямо в браузері
- 📱 **Працює на Android** — Termux як сервер, браузер як клієнт
- 📡 **Доступний з мережі** — відкрий чат з комп'ютера в тій же Wi-Fi
- 📷 **Медіа-вкладення** — фото, галерея, голосові, файли
- 🎤 **Голосові повідомлення** — запис через мікрофон прямо в браузері
- 💾 **Сесії** — декілька чатів з історією, перемикання між ними
- 🛠 **Інструменти** — швидкі команди (термінал, файли, Python, HTTP)
- 📥 **Експорт чатів** — збереження в Markdown
- ⚙️ **Налаштування Hermes** — вибір моделі, провайдера, інструментів
- 🔄 **Автозапуск** — сервер стартує разом з Termux

## 📋 Вимоги

- **Android** (будь-яка версія)
- **Termux** ([F-Droid](https://f-droid.org/packages/com.termux/) або GitHub)
- **Git** (встановлюється автоматично)

## ⚡ Встановлення

### Спосіб 1: Швидкий старт (однією командою)

```bash
# Відкрий Termux і виконай:
curl -fsSL https://raw.githubusercontent.com/Fil-m/hermonoid/main/scripts/install.sh | bash
```

### Спосіб 2: Вручну

```bash
# 1. Клонуй репозиторій
git clone https://github.com/Fil-m/hermonoid.git ~/hermonoid

# 2. Запусти інсталятор
python3 ~/hermonoid/scripts/hermonoid.py

# 3. Слідуй інструкції на екрані
```

### Спосіб 3: З Hermes Chat (якщо вже є)

```bash
cd ~/hermes_chat
# Скопіюй проект
cp -r ~/hermes_chat ~/hermonoid
# Запусти налаштування
python3 ~/hermonoid/scripts/hermonoid.py
```

## 🎮 Команди

Після встановлення доступні команди:

| Команда | Дія |
|---------|-----|
| `hermonoid` або `hchat` | Запустити веб-чат |
| `hstart` | Запустити сервер у фоні |
| `hstop` | Зупинити сервер |
| `hstatus` | Перевірити статус |
| `hlog` | Переглянути логи |
| `hupdate` | Оновити з GitHub |
| `hsetup` | Повторне налаштування |

## 🌐 Веб-інтерфейс

Після запуску відкрий в браузері:

- **На телефоні:** `http://localhost:8080`
- **З комп'ютера:** `http://IP_ТЕЛЕФОНУ:8080`

### Функції інтерфейсу:

- **Сайдбар** — список сесій з назвами та кількістю повідомлень
- **Поле вводу** — з підтримкою медіа (📎 фото, галерея, голос, файл)
- **Інструменти** — швидкі кнопки для команд (cmd, read, py, write, find, http)
- **Контекстне меню** — правий клік на сесії (перейменувати/видалити)
- **Перегляд зображень** — клік на фото для перегляду на весь екран
- **Експорт** — збереження історії в Markdown

## 🔧 API

Сервер надає REST API для інтеграцій:

| Метод | Шлях | Опис |
|-------|------|------|
| `GET` | `/api/status` | Статус сервера |
| `GET` | `/api/sessions` | Список сесій |
| `POST` | `/api/sessions` | Створити сесію |
| `GET` | `/api/sessions/:id` | Сесія + повідомлення |
| `POST` | `/api/sessions/:id/rename` | Перейменувати |
| `DELETE` | `/api/sessions/:id` | Видалити сесію |
| `POST` | `/api/chat` | Надіслати повідомлення |
| `POST` | `/api/exec` | Виконати shell команду |

## 📁 Структура проекту

```
~/hermonoid/
├── server/
│   └── server.py        # HTTP сервер + API (Python)
├── web/
│   └── index.html       # Веб-клієнт (HTML + CSS + JS)
├── scripts/
│   ├── hermonoid.py     # Інсталятор з налаштуваннями
│   ├── install.sh       # Bash-інсталятор (curl | bash)
│   └── start-chat.sh    # Скрипт автозапуску
├── config/              # Конфігураційні файли
├── sessions.db          # SQLite з сесіями (створюється)
├── server.log           # Лог сервера (створюється)
└── README.md            # Цей файл
```

## 🤖 Як це працює

1. **Hermes Agent** працює як CLI-агент на телефоні
2. **Python HTTP сервер** приймає запити з веб-браузера
3. **Веб-інтерфейс** (HTML/CSS/JS) робить POST запити до сервера
4. **Сервер** передає повідомлення Hermes через CLI і повертає відповідь
5. **SQLite** зберігає сесії та історію повідомлень

## 🧪 Розробка

```bash
# Клонувати
git clone git@github.com:Fil-m/hermonoid.git
cd hermonoid

# Запустити сервер вручну
python3 server/server.py

# Запустити в фоні
python3 server/server.py &

# Перевірити
curl http://localhost:8080/api/status
```

## 📜 Ліцензія

MIT

## 🙌 Автор

**Fil-m** — Hermonoid створено як обгортку для Hermes Agent від Nous Research.
