# Тренажёр для подготовки к экзаменам

Веб-приложение для подготовки к экзаменам с отслеживанием прогресса. Поддерживает три способа авторизации: по Secret-строке (браузер), через Telegram Mini App и через MAX Mini App.

## Возможности

- 🔐 **Авторизация по Secret строкам** — индивидуальный доступ для веб-версии
- 🤖 **Telegram Mini App** — запуск прямо из Telegram без ввода паролей
- 💬 **MAX Mini App** — запуск прямо из мессенджера MAX без ввода паролей
- 📊 **Отслеживание прогресса** — персональная статистика для каждого пользователя
- 📝 **Режим обучения** — просмотр вопросов с проверкой ответов
- 🧪 **Режим тестирования** — проверка знаний в режиме экзамена
- 📈 **Статистика** — детальная статистика по экзамену и разделам
- 📚 **Поддержка нескольких экзаменов** — переключение между различными экзаменами
- 💾 **Автосохранение сессии** — авторизация сохраняется между сеансами

## Установка

### Требования

- Python 3.9 или выше
- pip

### Шаги установки

1. Клонируйте репозиторий:
```bash
git clone https://github.com/ваш-username/exam_trainer.git
cd exam_trainer
```

2. Создайте виртуальное окружение (рекомендуется):
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

## Настройка и запуск

### 1. Создание Secret для пользователей

Перед первым запуском создайте Secret строки для пользователей:

```bash
python generate_secret.py
```

Скрипт создаст:
- Новую Secret строку
- Папку `secrets/{secret}/` с файлом прогресса
- Зарегистрирует Secret в `secrets_config.json`

**Важно:** Сохраните выведенную Secret строку в безопасном месте. Она используется для входа в браузерную версию.

### 2. Переменные окружения

| Переменная | Назначение | Обязательность |
|---|---|---|
| `SECRET_KEY` | Ключ подписи Flask-сессий | Рекомендуется для production |
| `TELEGRAM_BOT_TOKEN` | Токен бота Telegram | Только для Telegram Mini App |
| `TELEGRAM_AUTH_MAX_AGE_SECONDS` | Максимальный возраст initData (по умолчанию `86400`) | Нет |
| `MAX_BOT_TOKEN` | Токен бота MAX | Только для MAX Mini App |
| `MAX_AUTH_MAX_AGE_SECONDS` | Максимальный возраст initData (по умолчанию `86400`) | Нет |
| `SECRETS_DIR` | Путь к папке с данными пользователей (по умолчанию `./secrets`) | Нет |
| `SECRETS_CONFIG_PATH` | Путь к `secrets_config.json` | Нет |
| `EXAM_DATA_DIR` | Путь к папке с данными экзаменов | Нет |

```bash
export SECRET_KEY=ваш-секретный-ключ
export TELEGRAM_BOT_TOKEN=ваш-токен-telegram
export MAX_BOT_TOKEN=ваш-токен-max
```

### 3. Запуск приложения

```bash
python trainer_app.py
```

Приложение будет доступно по адресу: **http://localhost:5002**

## Режимы работы

### Веб-версия (Secret)

URL: `https://ваш-домен.com/`

Авторизация по Secret-строке, которую генерирует `generate_secret.py`. Подходит для доступа через браузер без мессенджера.

### Telegram Mini App

URL мини-приложения: `https://ваш-домен.com/telegram`

#### Настройка

1. **Создайте бота** через [@BotFather](https://t.me/BotFather):
   - Отправьте `/newbot`, следуйте инструкциям, сохраните токен

2. **Установите переменную окружения**:
   ```bash
   export TELEGRAM_BOT_TOKEN=ваш-токен-бота
   ```

3. **Настройте Main Mini App** в @BotFather:
   - `Bot Settings → Configure Mini App → Enable Mini App`
   - URL: `https://ваш-домен.com/telegram` (только HTTPS)

4. **Запуск**: откройте бота в Telegram и нажмите кнопку «Запустить», или используйте ссылку:
   ```
   https://t.me/ваш_бот?startapp
   ```

#### Особенности

- Автоматическая авторизация через `initData` — без ввода Secret
- Прогресс привязан к Telegram-аккаунту
- Адаптивная тема (светлая/тёмная) из настроек Telegram
- Работает на iOS, Android, Desktop, Web

### MAX Mini App

URL мини-приложения: `https://ваш-домен.com/max`

MAX — мессенджер от [VK](https://max.ru). Мини-приложения работают аналогично Telegram Mini Apps.

#### Настройка

1. **Создайте бота** на [платформе MAX для партнёров](https://dev.max.ru):
   - Зарегистрируйте организацию, создайте чат-бот, получите токен бота

2. **Установите переменную окружения**:
   ```bash
   export MAX_BOT_TOKEN=ваш-токен-бота-max
   ```

3. **Подключите мини-приложение**:
   - В панели управления ботом: `Чат-бот и мини-приложение → Настроить`
   - URL: `https://ваш-домен.com/max` (только HTTPS)
   - Выберите вид кнопки открытия и нажмите «Сохранить»

4. **Запуск**: откройте бота в MAX — в чате появится кнопка, или используйте диплинк:
   ```
   https://max.ru/ваш_бот?startapp
   ```

#### Особенности

- Автоматическая авторизация через `initData` — без ввода Secret
- Прогресс привязан к MAX-аккаунту
- Использует MAX Bridge (`window.WebApp`)
- Работает на iOS, Android, Desktop, Web

## Хранение данных пользователей

| Режим | Путь к прогрессу |
|---|---|
| Веб (Secret) | `secrets/{secret}/trainer_progress.json` |
| Telegram | `secrets/tg_{user_id}/trainer_progress.json` |
| MAX | `secrets/max_{user_id}/trainer_progress.json` |

Все режимы работают независимо и не конфликтуют.

## Запуск в Docker

```bash
docker compose up -d
```

Для первого запуска создайте Secret:
```bash
docker compose run --rm generate-secret
```

### Переменные окружения для Docker

Скопируйте пример и заполните:
```bash
cp local-test/.env.example .env
# Отредактируйте .env
```

Ключевые переменные в `docker-compose.yaml`:

```yaml
environment:
  - SECRET_KEY=${SECRET_KEY}
  - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}   # опционально
  - MAX_BOT_TOKEN=${MAX_BOT_TOKEN}              # опционально
  - SECRETS_DIR=/app/secrets
  - SECRETS_CONFIG_PATH=/app/secrets/secrets_config.json
  - EXAM_DATA_DIR=/app/secrets
```

Данные пользователей хранятся в томе `./secrets:/app/secrets`.

## Структура проекта

```
exam_trainer/
├── trainer_app.py              # Основное приложение Flask
├── telegram_auth.py            # Валидация initData (Telegram и MAX)
├── exam_editor_models.py       # Модели данных для работы с вопросами
├── generate_secret.py          # Скрипт генерации Secret строк
├── requirements.txt            # Зависимости Python
│
├── templates/
│   ├── trainer.html            # Веб-версия (Secret)
│   ├── telegram_trainer.html   # Telegram Mini App
│   └── max_trainer.html        # MAX Mini App
│
├── sources/                    # Данные экзаменов (не в Git)
│   ├── exam_config.json
│   └── *_exam_questions.json
│
├── static/                     # Статические файлы
│
├── secrets/                    # Данные пользователей (не в Git)
│   ├── {secret}/               # Веб-пользователи
│   ├── tg_{user_id}/           # Telegram-пользователи
│   └── max_{user_id}/          # MAX-пользователи
│
├── Dockerfile
├── docker-compose.yaml
└── local-test/
    ├── docker-compose.yaml     # Compose с образом из Docker Hub
    └── .env.example
```

## API Endpoints

**Страницы:**
- `GET /` — веб-версия (авторизация по Secret)
- `GET /telegram` — Telegram Mini App
- `GET /max` — MAX Mini App

**Авторизация:**
- `POST /api/auth/login` — вход по Secret
- `POST /api/auth/telegram` — авторизация через Telegram initData
- `POST /api/auth/max` — авторизация через MAX initData
- `POST /api/auth/logout` — выход
- `GET /api/auth/status` — статус авторизации

**Данные** (требуют авторизации):
- `GET /api/exams` — список экзаменов
- `GET /api/questions` — вопросы с фильтрацией
- `GET /api/sections` — разделы экзамена
- `GET /api/statistics` — статистика
- `GET /api/question/<id>` — конкретный вопрос
- `POST /api/question/<id>/check` — проверка ответа
- `POST /api/question/<id>/mastered` — статус «Усвоен»
- `POST /api/session/start` — начало теста
- `POST /api/session/results` — результаты теста

**Диагностика:**
- `GET /api/health` — версия кода и список зарегистрированных маршрутов

## Устранение неполадок Mini App

### Ошибка авторизации

1. Проверьте, что токен бота установлен:
   ```bash
   # Telegram
   echo $TELEGRAM_BOT_TOKEN

   # MAX
   echo $MAX_BOT_TOKEN
   ```

2. Проверьте логи — в них указана точная причина отказа:
   ```bash
   # Docker
   docker compose logs -f app

   # Kubernetes
   kubectl logs <pod-name> -f
   ```

   Что искать в логах:

   | Сообщение | Причина | Решение |
   |---|---|---|
   | `Missing 'hash' field` | initData не содержит hash | Проверить формат initData |
   | `auth_date age: NNN > 86400` | initData устарел | Переоткрыть приложение |
   | `Hash mismatch!` | Токен не совпадает | Сверить токен с панелью управления |
   | `token_prefix=EMPTY` | Переменная не задана | Установить переменную окружения |

3. Проверьте URL Mini App:
   - Telegram: должен указывать на `/telegram`
   - MAX: должен указывать на `/max`
   - Обязательно HTTPS в production

## Безопасность

- `secrets/` и `secrets_config.json` исключены из Git
- Не коммитьте Secret-строки пользователей
- В production обязательно устанавливайте `SECRET_KEY`
- Токены ботов храните в переменных окружения, не в коде
