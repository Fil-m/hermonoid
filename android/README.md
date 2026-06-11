# Hermonoid APK — Android WebView додаток

**Web-чат для Hermes Agent на Android.** Цей додаток використовує WebView для відображення інтерфейсу Hermonoid.

## Вимоги

- Android 8.0 (API 26) або вище
- Встановлений Termux з Hermonoid сервером
- Сервер Hermonoid на `http://localhost:8080`

## Як зібрати APK

### GitHub Actions (рекомендовано)

1. Онови токен GitHub: `gh auth refresh --scopes workflow`
2. Зроби пуш в main — APK збереться автоматично
3. Скачай APK з вкладки **Actions** → **Build Hermonoid APK** → Artifacts

### Локальна збірка (Android Studio)

1. Відкрий папку `android/` в Android Studio
2. `Build` → `Build Bundle(s) / APK(s)` → `Build APK(s)`
3. APK буде в `app/build/outputs/apk/release/`

### Локальна збірка (командний рядок)

```bash
cd android
chmod +x gradlew
./gradlew assembleRelease
```

## Як це працює

1. Встановлюєш Termux + Hermes Agent + Hermonoid
2. Запускаєш сервер (`hurl` або через віджет)
3. Відкриваєш цей додаток
4. WebView показує чат Hermonoid з `http://localhost:8080`

## Функції

- 📱 Повноекранний режим (без адресного рядка)
- 🗂 Завантаження файлів (через File Chooser)
- 🔙 Кнопка "Назад" для навігації
- 🔄 Swipe-to-refresh (оновлення)
- 🎙 Голосові повідомлення
