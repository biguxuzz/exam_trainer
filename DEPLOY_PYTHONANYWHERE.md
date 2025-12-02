# Инструкция по деплою на PythonAnywhere.com

## Подготовка

### Требования
- Аккаунт на [PythonAnywhere.com](https://www.pythonanywhere.com) (бесплатный или платный)
- Проект должен быть в репозитории GitHub (или другой Git-репозиторий)

## Шаг 1: Регистрация и вход

1. Зарегистрируйтесь на [pythonanywhere.com](https://www.pythonanywhere.com)
2. Войдите в аккаунт
3. Перейдите в раздел **"Web"** (в верхнем меню)

## Шаг 2: Создание нового веб-приложения

1. Нажмите **"Add a new web app"**
2. Выберите **"Manual configuration"** (не Flask starter)
3. Выберите версию Python (рекомендуется Python 3.10 или выше, включая 3.13)
4. Нажмите **"Next"**

## Шаг 3: Клонирование репозитория

### Вариант A: Через Git (рекомендуется)

1. Откройте вкладку **"Consoles"** → **"Bash"**
2. Перейдите в домашнюю директорию:
   ```bash
   cd ~
   ```
3. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/ваш-username/exam_trainer.git
   ```
   Или используйте SSH:
   ```bash
   git clone git@github.com:ваш-username/exam_trainer.git
   ```

### Вариант B: Загрузка файлов через веб-интерфейс

1. Откройте **"Files"** в верхнем меню
2. Перейдите в `home/ваш-username/`
3. Загрузите файлы проекта через веб-интерфейс

## Шаг 4: Настройка виртуального окружения

1. В консоли Bash выполните:
   ```bash
   cd ~/exam_trainer
   python3.13 -m venv venv
   # Замените python3.13 на вашу версию Python (python3.10, python3.11, python3.12 и т.д.)
   ```

2. Активируйте виртуальное окружение:
   ```bash
   source venv/bin/activate
   ```

3. Установите зависимости:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Шаг 5: Создание структуры папок для данных

В консоли Bash выполните:
```bash
cd ~/exam_trainer
mkdir -p secrets
```

## Шаг 6: Создание Secret строк для пользователей

1. В консоли Bash (с активированным venv):
   ```bash
   cd ~/exam_trainer
   source venv/bin/activate
   python generate_secret.py
   ```

2. Сохраните выведенную Secret строку - она понадобится для входа в приложение

3. Повторите для каждого пользователя

## Шаг 7: Настройка WSGI файла

1. Вернитесь в раздел **"Web"**
2. Найдите секцию **"WSGI configuration file"**
3. Нажмите на ссылку для редактирования файла
4. **Важно:** Сначала определите версию Python вашего виртуального окружения:
   ```bash
   cd ~/exam_trainer
   source venv/bin/activate
   python --version
   ```
   Запомните версию (например, Python 3.10, 3.11, 3.12, 3.13 и т.д.)

5. Замените содержимое WSGI файла на:

```python
# +++++++++++ FLASK +++++++++++
# Flask works like any other WSGI-compatible framework, we just need
# to import the application.  Often Flask apps are called "app" so we
# may need to rename it during import to avoid conflicts.

import sys
import os

# Путь к вашему проекту
project_home = '/home/ваш-username/exam_trainer'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Путь к site-packages виртуального окружения
# Замените python3.13 на вашу версию Python (3.10, 3.11, 3.12, 3.13 и т.д.)
venv_site_packages = '/home/ваш-username/exam_trainer/venv/lib/python3.13/site-packages'
# Примеры для других версий:
# venv_site_packages = '/home/ваш-username/exam_trainer/venv/lib/python3.12/site-packages'
# venv_site_packages = '/home/ваш-username/exam_trainer/venv/lib/python3.11/site-packages'
# venv_site_packages = '/home/ваш-username/exam_trainer/venv/lib/python3.10/site-packages'

if venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)

# Импортируем приложение
from trainer_app import app as application

# Если вы используете переменные окружения, установите их здесь
# os.environ['SECRET_KEY'] = 'ваш-секретный-ключ-для-production'
```

**Важно:** 
- Замените `ваш-username` на ваш реальный username на PythonAnywhere
- Замените `python3.13` на вашу версию Python (например, `python3.12`, `python3.11`, `python3.10`), если используете другую версию
- Путь к `site-packages` должен точно соответствовать версии Python вашего виртуального окружения
- Проверьте версию командой: `source venv/bin/activate && python --version`

## Шаг 8: Настройка статических файлов

1. В разделе **"Web"** найдите секцию **"Static files"**
2. Добавьте следующие маппинги:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/ваш-username/exam_trainer/static/` |

Если папка `static` пустая, создайте её:
```bash
mkdir -p ~/exam_trainer/static
```

## Шаг 9: Настройка переменных окружения (опционально)

1. В разделе **"Web"** найдите секцию **"Environment variables"**
2. Добавьте переменную (если нужно):
   ```
   SECRET_KEY=ваш-секретный-ключ-для-production
   ```

**Рекомендация:** Используйте длинный случайный ключ для production.

## Шаг 10: Настройка путей в приложении

Убедитесь, что в `trainer_app.py` используются относительные пути или пути относительно домашней директории. Если нужно, можно добавить проверку:

```python
import os

# Определяем базовую директорию
if os.path.exists('/home'):
    # Мы на PythonAnywhere
    BASE_DIR = os.path.expanduser('~/exam_trainer')
else:
    # Локальная разработка
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRETS_DIR = os.path.join(BASE_DIR, "secrets")
SECRETS_CONFIG_FILE = os.path.join(BASE_DIR, "secrets_config.json")
```

## Шаг 11: Проверка прав доступа

Убедитесь, что папка `secrets` имеет права на запись:

```bash
chmod 755 ~/exam_trainer/secrets
```

## Шаг 12: Запуск приложения

1. В разделе **"Web"** нажмите кнопку **"Reload"** (зеленая кнопка)
2. Дождитесь перезагрузки (обычно несколько секунд)
3. Откройте ваш сайт по адресу: `https://ваш-username.pythonanywhere.com`

## Шаг 13: Проверка работы

1. Откройте ваш сайт в браузере
2. Должна появиться форма авторизации
3. Введите Secret строку, созданную на шаге 6
4. Проверьте работу всех функций:
   - Загрузка экзаменов
   - Просмотр вопросов
   - Режим тестирования
   - Сохранение прогресса

## Решение проблем

### Проблема: Ошибка импорта модулей

**Решение:**
1. **Способ 1 (рекомендуется):** Используйте настройку Virtualenv в веб-интерфейсе:
   - Web → Virtualenv → укажите `/home/ваш-username/exam_trainer/venv`
   - Это автоматически добавит пути к библиотекам
   - Используйте упрощенный WSGI файл (см. альтернативный способ в Шаге 7)

2. **Способ 2:** Если используете ручную настройку в WSGI файле:
   - Проверьте версию Python в виртуальном окружении:
     ```bash
     cd ~/exam_trainer
     source venv/bin/activate
     python --version
     ```
   - Убедитесь, что путь к `site-packages` в WSGI файле соответствует версии Python
   - Проверьте, что путь существует:
     ```bash
     ls -la ~/exam_trainer/venv/lib/python3.13/site-packages
     # Замените python3.13 на вашу версию (python3.12, python3.11, python3.10 и т.д.)
     ```

3. Проверьте, что все зависимости установлены:
   ```bash
   source venv/bin/activate
   pip list
   ```

4. Проверьте пути в WSGI файле - все пути должны быть абсолютными

### Проблема: 500 Internal Server Error

**Решение:**
1. Откройте **"Web"** → **"Error log"**
2. Проверьте ошибки в логе
3. Частые причины:
   - Неправильные пути к файлам
   - Отсутствие прав на запись в папку `secrets`
   - Не установлены зависимости

### Проблема: Статические файлы не загружаются

**Решение:**
- Проверьте настройки Static files в разделе "Web"
- Убедитесь, что пути указаны правильно
- Проверьте права доступа к папке `static`

### Проблема: Сессия не сохраняется

**Решение:**
- Убедитесь, что `session.permanent = True` установлено
- Проверьте, что `SECRET_KEY` установлен
- Проверьте настройки cookies в браузере

### Проблема: Не могу создать Secret

**Решение:**
```bash
cd ~/exam_trainer
source venv/bin/activate
python generate_secret.py
```

Убедитесь, что:
- Виртуальное окружение активировано
- Вы находитесь в правильной директории
- Папка `secrets` существует и имеет права на запись

## Обновление приложения

Когда нужно обновить код:

1. В консоли Bash:
   ```bash
   cd ~/exam_trainer
   git pull origin main
   # или git pull origin master
   ```

2. Если изменились зависимости:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. В разделе **"Web"** нажмите **"Reload"**

## Настройка домена (для платных аккаунтов)

1. В разделе **"Web"** найдите **"Domains"**
2. Добавьте ваш домен
3. Настройте DNS записи согласно инструкциям PythonAnywhere
4. После настройки DNS нажмите **"Reload"**

## Резервное копирование

Рекомендуется регулярно делать резервные копии:

1. **Данные пользователей:**
   ```bash
   tar -czf secrets_backup_$(date +%Y%m%d).tar.gz ~/exam_trainer/secrets
   ```

2. **Конфигурация:**
   ```bash
   cp ~/exam_trainer/secrets_config.json ~/secrets_config_backup.json
   ```

3. **Загрузите архивы** на ваш компьютер или облачное хранилище

## Ограничения бесплатного аккаунта

- Приложение "засыпает" после неактивности (нужно "разбудить" первым запросом)
- Ограниченное количество внешних запросов
- Один веб-приложение
- Поддомен `ваш-username.pythonanywhere.com`

## Полезные команды

```bash
# Просмотр логов ошибок
tail -f ~/exam_trainer/error.log

# Проверка процессов
ps aux | grep python

# Проверка использования диска
du -sh ~/exam_trainer

# Просмотр установленных пакетов
source venv/bin/activate
pip list
```

## Дополнительные настройки безопасности

1. **Используйте HTTPS** (включено по умолчанию на PythonAnywhere)
2. **Установите сильный SECRET_KEY** через переменные окружения
3. **Регулярно обновляйте зависимости:**
   ```bash
   pip install --upgrade flask flask-cors
   ```
4. **Ограничьте доступ к папке secrets:**
   ```bash
   chmod 700 ~/exam_trainer/secrets
   ```

## Контакты и поддержка

- Документация PythonAnywhere: https://help.pythonanywhere.com/
- Форум поддержки: https://www.pythonanywhere.com/forums/

