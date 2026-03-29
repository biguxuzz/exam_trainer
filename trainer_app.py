"""
Веб-приложение тренажёр для подготовки к экзаменам
"""
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from functools import wraps
from exam_editor_models import QuestionBank, Question
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import telegram_auth

app = Flask(__name__)

# ВАЖНО: SECRET_KEY должен быть установлен через переменную окружения!
# Генерация: python -c "import secrets; print(secrets.token_hex(32))"
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    logging.warning("⚠️  SECRET_KEY не установлен! Используется небезопасный ключ для разработки.")
    logging.warning("⚠️  Для продакшена установите: export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')")
    _secret_key = 'dev-secret-key-UNSAFE-change-in-production'
app.secret_key = _secret_key

# Настройка постоянных сессий (30 дней)
app.permanent_session_lifetime = timedelta(days=30)

# CORS: в продакшене лучше указать конкретные домены
CORS(app, supports_credentials=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Конфигурация Secret
# Определяем базовую директорию проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Путь к конфигу/папке можно переопределить через окружение (удобно для Docker volume)
SECRETS_CONFIG_FILE = os.environ.get("SECRETS_CONFIG_PATH") or os.path.join(BASE_DIR, "secrets_config.json")
SECRETS_DIR = os.environ.get("SECRETS_DIR") or os.path.join(BASE_DIR, "secrets")

# Глобальный словарь для хранения экземпляров UserProgress по Secret
user_progress_cache: Dict[str, 'UserProgress'] = {}

# Кэш банков вопросов для каждого экзамена
question_bank_cache: Dict[str, QuestionBank] = {}

# Защита от брутфорса: {ip: {"attempts": int, "blocked_until": datetime}}
login_attempts: Dict[str, Dict] = {}
MAX_LOGIN_ATTEMPTS = 5
BLOCK_DURATION_MINUTES = 15

# Экзамен по умолчанию
DEFAULT_EXAM_NAME = "1С:Руководитель проекта"

# Конфигурация Telegram Mini App
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_AUTH_MAX_AGE_SECONDS = int(os.environ.get('TELEGRAM_AUTH_MAX_AGE_SECONDS', '86400'))

# Конфигурация MAX Mini App
MAX_BOT_TOKEN = os.environ.get('MAX_BOT_TOKEN', '').strip()
MAX_AUTH_MAX_AGE_SECONDS = int(os.environ.get('MAX_AUTH_MAX_AGE_SECONDS', '86400'))


def get_question_bank(exam_name: str) -> QuestionBank:
    """Получение банка вопросов для экзамена (с кэшированием)"""
    if exam_name not in question_bank_cache:
        question_bank_cache[exam_name] = QuestionBank(exam_name)
    return question_bank_cache[exam_name]


def get_current_exam_name() -> str:
    """Получение текущего экзамена из сессии пользователя"""
    return session.get('current_exam', DEFAULT_EXAM_NAME)


def set_current_exam_name(exam_name: str):
    """Установка текущего экзамена в сессии пользователя"""
    session['current_exam'] = exam_name


def load_secrets():
    """Загрузка списка зарегистрированных Secret"""
    if not os.path.exists(SECRETS_CONFIG_FILE):
        return []
    
    try:
        with open(SECRETS_CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("secrets", [])
    except Exception as e:
        logging.error(f"Ошибка загрузки конфигурации Secret: {e}")
        return []


def register_max_user(max_user_id: int, username: str = None):
    """Регистрация MAX пользователя в secrets_config.json"""
    user_key = f"max_{max_user_id}"

    secrets_list = []
    config_data = {}

    if os.path.exists(SECRETS_CONFIG_FILE):
        try:
            with open(SECRETS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                secrets_list = config_data.get("secrets", [])
        except Exception as e:
            logging.error(f"Ошибка чтения конфигурации: {e}")
            secrets_list = []

    if user_key in secrets_list:
        logging.debug(f"MAX user {max_user_id} уже зарегистрирован")
        return

    secrets_list.append(user_key)
    config_data["secrets"] = secrets_list

    if "max_users" not in config_data:
        config_data["max_users"] = {}

    config_data["max_users"][str(max_user_id)] = {
        "user_key": user_key,
        "username": username,
        "registered_at": datetime.now().isoformat()
    }

    try:
        temp_file = SECRETS_CONFIG_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, SECRETS_CONFIG_FILE)
        logging.info(f"MAX user {max_user_id} (@{username or 'no_username'}) зарегистрирован в secrets_config.json")
    except Exception as e:
        logging.error(f"Ошибка сохранения конфигурации для MAX user {max_user_id}: {e}")


def register_telegram_user(telegram_user_id: int, username: str = None):
    """Регистрация Telegram пользователя в secrets_config.json"""
    user_key = f"tg_{telegram_user_id}"
    
    # Загружаем существующие секреты
    secrets_list = []
    config_data = {}
    
    if os.path.exists(SECRETS_CONFIG_FILE):
        try:
            with open(SECRETS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                secrets_list = config_data.get("secrets", [])
        except Exception as e:
            logging.error(f"Ошибка чтения конфигурации: {e}")
            secrets_list = []
    
    # Проверяем, не существует ли уже такой пользователь
    if user_key in secrets_list:
        logging.debug(f"Telegram user {telegram_user_id} уже зарегистрирован")
        return
    
    # Добавляем нового пользователя
    secrets_list.append(user_key)
    config_data["secrets"] = secrets_list
    
    # Добавляем метаданные Telegram пользователей (опционально)
    if "telegram_users" not in config_data:
        config_data["telegram_users"] = {}
    
    config_data["telegram_users"][str(telegram_user_id)] = {
        "user_key": user_key,
        "username": username,
        "registered_at": datetime.now().isoformat()
    }
    
    # Сохраняем обновлённую конфигурацию
    try:
        # Атомарное сохранение через временный файл
        temp_file = SECRETS_CONFIG_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, SECRETS_CONFIG_FILE)
        logging.info(f"Telegram user {telegram_user_id} (@{username or 'no_username'}) зарегистрирован в secrets_config.json")
    except Exception as e:
        logging.error(f"Ошибка сохранения конфигурации для Telegram user {telegram_user_id}: {e}")


def is_valid_secret(secret: str) -> bool:
    """Проверка валидности Secret"""
    if not secret:
        logging.debug("Secret validation failed: empty secret")
        return False
    
    # Защита от Path Traversal - secret должен быть простой строкой без спецсимволов
    if not secret.isalnum() or len(secret) < 16 or len(secret) > 64:
        logging.warning(f"Secret validation failed: invalid format (len={len(secret)}, alnum={secret.isalnum()})")
        return False
    
    # Проверяем, зарегистрирован ли Secret (проверяем СНАЧАЛА в списке, потом папку)
    registered_secrets = load_secrets()
    if secret not in registered_secrets:
        logging.warning(f"Secret validation failed: not in registered list (registered: {len(registered_secrets)} secrets)")
        return False
    
    # Проверяем, существует ли папка для этого Secret
    secret_dir = os.path.join(SECRETS_DIR, secret)
    if not os.path.exists(secret_dir):
        logging.warning(f"Secret validation failed: directory not found: {secret_dir}")
        return False
    
    return True


def get_user_progress(secret: str) -> 'UserProgress':
    """Получение или создание экземпляра UserProgress для Secret"""
    if secret not in user_progress_cache:
        progress_file = os.path.join(SECRETS_DIR, secret, "trainer_progress.json")
        user_progress_cache[secret] = UserProgress(progress_file)
    return user_progress_cache[secret]


def get_max_user_progress(max_user_id: int) -> 'UserProgress':
    """Получение или создание экземпляра UserProgress для MAX user_id"""
    user_key = f"max_{max_user_id}"
    if user_key not in user_progress_cache:
        max_user_dir = os.path.join(SECRETS_DIR, user_key)
        os.makedirs(max_user_dir, exist_ok=True)
        progress_file = os.path.join(max_user_dir, "trainer_progress.json")
        user_progress_cache[user_key] = UserProgress(progress_file)
    return user_progress_cache[user_key]


def get_telegram_user_progress(telegram_user_id: int) -> 'UserProgress':
    """Получение или создание экземпляра UserProgress для Telegram user_id"""
    # Используем префикс tg_ для Telegram пользователей
    user_key = f"tg_{telegram_user_id}"
    if user_key not in user_progress_cache:
        # Создаём директорию для Telegram пользователя
        telegram_user_dir = os.path.join(SECRETS_DIR, user_key)
        os.makedirs(telegram_user_dir, exist_ok=True)
        progress_file = os.path.join(telegram_user_dir, "trainer_progress.json")
        user_progress_cache[user_key] = UserProgress(progress_file)
    return user_progress_cache[user_key]


def require_auth(f):
    """Декоратор для защиты маршрутов от неавторизованного доступа.
    
    Поддерживает два типа авторизации:
    1. Secret-based (для веб-версии)
    2. Telegram user_id (для Telegram Mini App)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Убеждаемся, что сессия постоянная
        session.permanent = True
        
        # Проверяем Telegram авторизацию
        telegram_user_id = session.get('telegram_user_id')
        if telegram_user_id:
            return f(*args, **kwargs)
        
        # Проверяем MAX авторизацию
        max_user_id = session.get('max_user_id')
        if max_user_id:
            return f(*args, **kwargs)
        
        # Проверяем Secret авторизацию (для веб-версии)
        secret = session.get('secret')
        if secret and is_valid_secret(secret):
            return f(*args, **kwargs)
        
        # Не авторизован
        return jsonify({"error": "Требуется авторизация", "authenticated": False}), 401
    return decorated_function


class UserProgress:
    """Класс для управления прогрессом пользователя.
    
    Данные всегда читаются с диска перед операциями чтения,
    чтобы обеспечить синхронизацию между разными устройствами.
    """
    
    def __init__(self, progress_file: str):
        self.progress_file = progress_file
        self.data: Dict[str, Dict] = {}  # exam_name -> {question_id -> progress}
        # Создаём директорию, если её нет
        progress_dir = os.path.dirname(progress_file)
        if progress_dir:
            os.makedirs(progress_dir, exist_ok=True)
    
    def load(self):
        """Загрузка прогресса из файла (вызывается перед каждой операцией)"""
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = {}
        except Exception as e:
            logging.error(f"Ошибка загрузки прогресса: {e}")
            self.data = {}
    
    def save(self):
        """Атомарное сохранение прогресса в файл"""
        try:
            # Сначала пишем во временный файл, потом переименовываем (атомарная операция)
            temp_file = self.progress_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            # Атомарная замена файла
            os.replace(temp_file, self.progress_file)
        except Exception as e:
            logging.error(f"Ошибка сохранения прогресса: {e}")
            # Удаляем временный файл при ошибке
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def get_question_progress(self, exam_name: str, question_id: str) -> Dict:
        """Получение прогресса по вопросу"""
        # Перечитываем данные с диска для синхронизации между устройствами
        self.load()
        exam_progress = self.data.get(exam_name, {})
        return exam_progress.get(question_id, {
            "attempts": 0,
            "correct_streak": 0,
            "total_correct": 0,
            "mastered": False,
            "last_attempt": None
        })
    
    def update_question_progress(self, exam_name: str, question_id: str, is_correct: bool, dont_know: bool = False):
        """Обновление прогресса по вопросу"""
        # Перечитываем данные с диска, чтобы не потерять изменения с другого устройства
        self.load()
        
        if exam_name not in self.data:
            self.data[exam_name] = {}
        
        if question_id not in self.data[exam_name]:
            self.data[exam_name][question_id] = {
                "attempts": 0,
                "correct_streak": 0,
                "total_correct": 0,
                "mastered": False,
                "last_attempt": None
            }
        
        progress = self.data[exam_name][question_id]
        progress["attempts"] += 1
        progress["last_attempt"] = datetime.now().isoformat()
        
        if dont_know:
            # Не знаю ответ - сбрасываем серию правильных ответов
            progress["correct_streak"] = 0
        elif is_correct:
            progress["correct_streak"] += 1
            progress["total_correct"] += 1
            # Если 3 правильных подряд - усвоено
            if progress["correct_streak"] >= 3:
                progress["mastered"] = True
        else:
            progress["correct_streak"] = 0
        
        self.save()
        return progress
    
    def set_mastered(self, exam_name: str, question_id: str, mastered: bool):
        """Установка/снятие отметки "Усвоен" """
        # Перечитываем данные с диска, чтобы не потерять изменения с другого устройства
        self.load()
        
        if exam_name not in self.data:
            self.data[exam_name] = {}
        
        if question_id not in self.data[exam_name]:
            self.data[exam_name][question_id] = {
                "attempts": 0,
                "correct_streak": 0,
                "total_correct": 0,
                "mastered": mastered,
                "last_attempt": None
            }
        else:
            self.data[exam_name][question_id]["mastered"] = mastered
            if not mastered:
                # При снятии отметки сбрасываем серию
                self.data[exam_name][question_id]["correct_streak"] = 0
        
        self.save()
        return self.data[exam_name][question_id]
    
    def get_exam_statistics(self, exam_name: str, verified_question_ids: List[str]) -> Dict:
        """Получение статистики по экзамену"""
        # Перечитываем данные с диска для синхронизации между устройствами
        self.load()
        exam_progress = self.data.get(exam_name, {})
        
        total_verified = len(verified_question_ids)
        mastered = 0
        attempted = 0
        total_attempts = 0
        total_correct = 0
        
        for q_id in verified_question_ids:
            progress = exam_progress.get(q_id, {})
            if progress.get("mastered", False):
                mastered += 1
            if progress.get("attempts", 0) > 0:
                attempted += 1
                total_attempts += progress.get("attempts", 0)
                total_correct += progress.get("total_correct", 0)
        
        return {
            "total_verified": total_verified,
            "mastered": mastered,
            "attempted": attempted,
            "not_attempted": total_verified - attempted,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "mastered_percent": round(mastered / total_verified * 100, 1) if total_verified > 0 else 0,
            "attempted_percent": round(attempted / total_verified * 100, 1) if total_verified > 0 else 0,
            "accuracy": round(total_correct / total_attempts * 100, 1) if total_attempts > 0 else 0
        }
    
    def get_section_statistics(self, exam_name: str, questions: List[Question]) -> List[Dict]:
        """Получение статистики по разделам"""
        # Перечитываем данные с диска для синхронизации между устройствами
        self.load()
        exam_progress = self.data.get(exam_name, {})
        
        sections: Dict[int, Dict] = {}
        
        for q in questions:
            if not q.is_verified:
                continue
            
            section_num = q.section_number or 0
            if section_num not in sections:
                sections[section_num] = {
                    "section_number": section_num,
                    "total": 0,
                    "mastered": 0,
                    "attempted": 0,
                    "total_correct": 0,
                    "total_attempts": 0
                }
            
            sections[section_num]["total"] += 1
            
            progress = exam_progress.get(q.id, {})
            if progress.get("mastered", False):
                sections[section_num]["mastered"] += 1
            if progress.get("attempts", 0) > 0:
                sections[section_num]["attempted"] += 1
                sections[section_num]["total_attempts"] += progress.get("attempts", 0)
                sections[section_num]["total_correct"] += progress.get("total_correct", 0)
        
        # Добавляем проценты
        result = []
        for section_num in sorted(sections.keys()):
            section = sections[section_num]
            section["mastered_percent"] = round(section["mastered"] / section["total"] * 100, 1) if section["total"] > 0 else 0
            section["attempted_percent"] = round(section["attempted"] / section["total"] * 100, 1) if section["total"] > 0 else 0
            section["accuracy"] = round(section["total_correct"] / section["total_attempts"] * 100, 1) if section["total_attempts"] > 0 else 0
            result.append(section)
        
        return result


# Функция для получения текущего user_progress из сессии
def get_current_user_progress() -> UserProgress:
    """Получение UserProgress для текущего авторизованного пользователя"""
    # Проверяем Telegram авторизацию
    telegram_user_id = session.get('telegram_user_id')
    if telegram_user_id:
        return get_telegram_user_progress(telegram_user_id)
    
    # Проверяем MAX авторизацию
    max_user_id = session.get('max_user_id')
    if max_user_id:
        return get_max_user_progress(max_user_id)
    
    # Проверяем Secret авторизацию
    secret = session.get('secret')
    if secret:
        return get_user_progress(secret)
    
    raise ValueError("Пользователь не авторизован")


@app.route('/')
def index():
    """Главная страница тренажёра"""
    return render_template('trainer.html')


@app.route('/telegram')
def telegram_app():
    """Telegram Mini App"""
    return render_template('telegram_trainer.html')


@app.route('/max')
def max_app():
    """MAX Mini App"""
    return render_template('max_trainer.html')


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Авторизация по Secret с защитой от брутфорса"""
    client_ip = request.remote_addr or 'unknown'
    
    # Проверяем, не заблокирован ли IP
    if client_ip in login_attempts:
        attempt_info = login_attempts[client_ip]
        if attempt_info.get("blocked_until"):
            if datetime.now() < attempt_info["blocked_until"]:
                remaining = (attempt_info["blocked_until"] - datetime.now()).seconds // 60
                return jsonify({
                    "error": f"Слишком много попыток. Попробуйте через {remaining + 1} мин.",
                    "authenticated": False
                }), 429
            else:
                # Блокировка истекла, сбрасываем
                login_attempts[client_ip] = {"attempts": 0, "blocked_until": None}
    
    data = request.get_json()
    secret = data.get('secret', '').strip() if data else ''
    
    if not secret:
        return jsonify({"error": "Secret не указан", "authenticated": False}), 400
    
    if not is_valid_secret(secret):
        # Увеличиваем счётчик неудачных попыток
        if client_ip not in login_attempts:
            login_attempts[client_ip] = {"attempts": 0, "blocked_until": None}
        login_attempts[client_ip]["attempts"] += 1
        
        # Блокируем после MAX_LOGIN_ATTEMPTS неудачных попыток
        if login_attempts[client_ip]["attempts"] >= MAX_LOGIN_ATTEMPTS:
            login_attempts[client_ip]["blocked_until"] = datetime.now() + timedelta(minutes=BLOCK_DURATION_MINUTES)
            logging.warning(f"IP {client_ip} заблокирован на {BLOCK_DURATION_MINUTES} мин после {MAX_LOGIN_ATTEMPTS} неудачных попыток")
        
        return jsonify({"error": "Неверный Secret", "authenticated": False}), 401
    
    # Успешный вход - сбрасываем счётчик
    if client_ip in login_attempts:
        del login_attempts[client_ip]
    
    # Сохраняем Secret в сессии и делаем сессию постоянной
    session['secret'] = secret
    session.permanent = True
    
    return jsonify({
        "success": True,
        "authenticated": True,
        "message": "Авторизация успешна"
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    session.pop('secret', None)
    session.pop('telegram_user_id', None)
    session.pop('telegram_username', None)
    session.pop('telegram_first_name', None)
    session.pop('telegram_last_name', None)
    session.pop('max_user_id', None)
    session.pop('max_username', None)
    session.pop('max_first_name', None)
    session.pop('max_last_name', None)
    return jsonify({
        "success": True,
        "authenticated": False,
        "message": "Выход выполнен"
    })


@app.route('/api/auth/status')
def auth_status():
    """Проверка статуса авторизации"""
    # Убеждаемся, что сессия постоянная
    session.permanent = True
    secret = session.get('secret')
    telegram_user_id = session.get('telegram_user_id')
    max_user_id = session.get('max_user_id')
    
    authenticated = (secret and is_valid_secret(secret)) or bool(telegram_user_id) or bool(max_user_id)
    
    return jsonify({
        "authenticated": authenticated,
        "has_secret": bool(secret),
        "has_telegram": bool(telegram_user_id),
        "has_max": bool(max_user_id)
    })


@app.route('/api/auth/telegram', methods=['POST'])
def telegram_login():
    """Авторизация через Telegram Mini App initData"""
    if not TELEGRAM_BOT_TOKEN:
        logging.error("TELEGRAM_BOT_TOKEN не установлен - проверьте переменную окружения")
        return jsonify({
            "error": "Telegram авторизация не настроена на сервере. Установите TELEGRAM_BOT_TOKEN.",
            "authenticated": False,
            "debug": "TELEGRAM_BOT_TOKEN не установлен"
        }), 500
    
    data = request.get_json()
    init_data = data.get('init_data', '').strip() if data else ''
    
    if not init_data:
        return jsonify({
            "error": "init_data не указан",
            "authenticated": False
        }), 400
    
    # Валидируем initData
    try:
        is_valid, telegram_data = telegram_auth.verify_telegram_init_data(
            init_data,
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_AUTH_MAX_AGE_SECONDS
        )
        
        if not is_valid or not telegram_data:
            # Парсим init_data для диагностики
            try:
                import urllib.parse
                parsed_params = dict(urllib.parse.parse_qsl(init_data))
                param_keys = sorted(parsed_params.keys())
                logging.warning(f"Telegram initData validation failed. Keys in init_data: {param_keys}")
                if 'signature' in parsed_params:
                    logging.warning("initData contains 'signature' - ensure signature is included in data_check_string")
            except Exception:
                pass
            
            logging.warning(f"Telegram initData validation failed. init_data length: {len(init_data)}, has_token: {bool(TELEGRAM_BOT_TOKEN)}")
            # Логируем первые 100 символов init_data для отладки (безопасно, так как это не секрет)
            if init_data:
                logging.debug(f"init_data preview: {init_data[:100]}...")
            return jsonify({
                "error": "Неверные данные авторизации Telegram. Проверьте, что TELEGRAM_BOT_TOKEN установлен правильно.",
                "authenticated": False
            }), 401
    except Exception as e:
        logging.error(f"Exception during Telegram initData validation: {e}", exc_info=True)
        return jsonify({
            "error": f"Ошибка валидации данных Telegram: {str(e)}",
            "authenticated": False
        }), 500
    
    # Извлекаем user_id из данных
    user_data = telegram_data.get('user')
    if not user_data:
        logging.warning("Telegram user data missing - возможно Mini App открыт не через Main Mini App")
        logging.debug(f"telegram_data keys: {list(telegram_data.keys())}")
        return jsonify({
            "error": "Данные пользователя Telegram не найдены. Убедитесь, что Mini App открыт через Telegram.",
            "authenticated": False
        }), 401
    
    if 'id' not in user_data:
        logging.warning(f"Telegram user data invalid - missing 'id' field. User data: {user_data}")
        return jsonify({
            "error": "Неверный формат данных пользователя Telegram",
            "authenticated": False
        }), 401
    
    telegram_user_id = user_data['id']
    telegram_username = user_data.get('username')
    
    # Регистрируем Telegram пользователя в secrets_config.json (если ещё не зарегистрирован)
    register_telegram_user(telegram_user_id, telegram_username)
    
    # Создаём папку и файл прогресса для пользователя (если ещё не созданы)
    get_telegram_user_progress(telegram_user_id)
    
    # Сохраняем данные в сессии
    session.permanent = True
    session['telegram_user_id'] = telegram_user_id
    session['telegram_username'] = telegram_username
    session['telegram_first_name'] = user_data.get('first_name')
    session['telegram_last_name'] = user_data.get('last_name')
    
    # Очищаем Secret сессию если была (чтобы не было конфликта)
    if 'secret' in session:
        del session['secret']
    
    logging.info(f"Telegram user authorized: {telegram_user_id} (@{telegram_username or 'no_username'})")
    
    return jsonify({
        "success": True,
        "authenticated": True,
        "user": {
            "id": telegram_user_id,
            "username": user_data.get('username'),
            "first_name": user_data.get('first_name'),
            "last_name": user_data.get('last_name')
        },
        "message": "Авторизация через Telegram успешна"
    })


@app.route('/api/auth/max', methods=['POST'])
def max_login():
    """Авторизация через MAX Mini App initData"""
    if not MAX_BOT_TOKEN:
        logging.error("MAX_BOT_TOKEN не установлен - проверьте переменную окружения")
        return jsonify({
            "error": "MAX авторизация не настроена на сервере. Установите MAX_BOT_TOKEN.",
            "authenticated": False,
            "debug": "MAX_BOT_TOKEN не установлен"
        }), 500

    data = request.get_json()
    init_data = data.get('init_data', '').strip() if data else ''

    if not init_data:
        return jsonify({
            "error": "init_data не указан",
            "authenticated": False
        }), 400

    # Валидируем initData (алгоритм идентичен Telegram)
    try:
        logging.info(f"MAX auth attempt: init_data length={len(init_data)}, "
                     f"token_prefix={MAX_BOT_TOKEN[:8] if MAX_BOT_TOKEN else 'EMPTY'}...")
        is_valid, max_data = telegram_auth.verify_telegram_init_data(
            init_data,
            MAX_BOT_TOKEN,
            MAX_AUTH_MAX_AGE_SECONDS,
            context="MAX"
        )

        if not is_valid or not max_data:
            logging.warning(f"MAX initData validation failed. "
                            f"init_data_len={len(init_data)}, "
                            f"token_set={bool(MAX_BOT_TOKEN)}, "
                            f"token_prefix={MAX_BOT_TOKEN[:8] if MAX_BOT_TOKEN else 'EMPTY'}... "
                            f"— проверьте логи выше для причины отказа")
            return jsonify({
                "error": "Неверные данные авторизации MAX. "
                         "Проверьте логи пода (kubectl logs) — там указана точная причина.",
                "authenticated": False
            }), 401
    except Exception as e:
        logging.error(f"Exception during MAX initData validation: {e}", exc_info=True)
        return jsonify({
            "error": f"Ошибка валидации данных MAX: {str(e)}",
            "authenticated": False
        }), 500

    # Извлекаем user_id из данных
    user_data = max_data.get('user')
    if not user_data:
        logging.warning("MAX user data missing")
        return jsonify({
            "error": "Данные пользователя MAX не найдены. Убедитесь, что мини-приложение открыто через MAX.",
            "authenticated": False
        }), 401

    if 'id' not in user_data:
        logging.warning(f"MAX user data invalid - missing 'id' field. User data: {user_data}")
        return jsonify({
            "error": "Неверный формат данных пользователя MAX",
            "authenticated": False
        }), 401

    max_user_id = user_data['id']
    max_username = user_data.get('username')

    # Регистрируем MAX пользователя в secrets_config.json
    register_max_user(max_user_id, max_username)

    # Создаём папку и файл прогресса для пользователя
    get_max_user_progress(max_user_id)

    # Сохраняем данные в сессии
    session.permanent = True
    session['max_user_id'] = max_user_id
    session['max_username'] = max_username
    session['max_first_name'] = user_data.get('first_name')
    session['max_last_name'] = user_data.get('last_name')

    # Очищаем другие сессии, если были
    for key in ('secret', 'telegram_user_id', 'telegram_username', 'telegram_first_name', 'telegram_last_name'):
        session.pop(key, None)

    logging.info(f"MAX user authorized: {max_user_id} (@{max_username or 'no_username'})")

    return jsonify({
        "success": True,
        "authenticated": True,
        "user": {
            "id": max_user_id,
            "username": max_username,
            "first_name": user_data.get('first_name'),
            "last_name": user_data.get('last_name')
        },
        "message": "Авторизация через MAX успешна"
    })


@app.route('/api/exams')
@require_auth
def get_exams():
    """Получение списка доступных экзаменов"""
    exams_info = QuestionBank.get_all_exams_info()
    exams = QuestionBank.get_available_exams()
    return jsonify({
        "exams": exams,
        "exams_info": exams_info,
        "current_exam": get_current_exam_name()
    })


@app.route('/api/exam/switch', methods=['POST'])
@require_auth
def switch_exam():
    """Переключение на другой экзамен"""
    data = request.get_json()
    exam_name = data.get("exam_name")
    
    if not exam_name:
        return jsonify({"error": "Не указано название экзамена"}), 400
    
    if exam_name not in QuestionBank.get_available_exams():
        return jsonify({"error": f"Экзамен '{exam_name}' не найден"}), 404
    
    try:
        # Устанавливаем экзамен в сессии пользователя
        set_current_exam_name(exam_name)
        
        # Получаем банк вопросов для этого экзамена
        question_bank = get_question_bank(exam_name)
        
        return jsonify({
            "success": True,
            "exam_name": exam_name,
            "questions_count": len([q for q in question_bank.questions if q.is_verified])
        })
    except Exception as e:
        logging.error(f"Ошибка переключения экзамена: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/questions')
@require_auth
def get_questions():
    """Получение списка вопросов с подтверждёнными ответами"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    hide_mastered = request.args.get('hide_mastered', 'true').lower() == 'true'
    section_filter = request.args.get('section', '').strip()
    status_filter = request.args.get('status', '').strip()
    search_query = request.args.get('search', '').strip()
    not_repeated_days = request.args.get('not_repeated_days', '').strip()
    
    # Фильтруем только вопросы с подтверждёнными ответами
    questions = [q for q in question_bank.questions 
                 if q.exam_name == current_exam_name and q.is_verified]
    
    # Фильтр по разделу
    if section_filter:
        try:
            section_num = int(section_filter)
            # Фильтруем вопросы, учитывая что section_number может быть None
            filtered_questions = [q for q in questions 
                                 if q.section_number is not None and q.section_number == section_num]
            if not filtered_questions and questions:
                # Логируем для отладки, если раздел не найден
                section_numbers = sorted(set(q.section_number for q in questions if q.section_number is not None))
                logging.warning(f"Раздел {section_num} не найден. Доступные разделы: {section_numbers}")
            questions = filtered_questions
        except ValueError:
            logging.error(f"Некорректный номер раздела: {section_filter}")
            pass
    
    # Поиск
    if search_query:
        query_lower = search_query.lower()
        questions = [q for q in questions 
                    if query_lower in q.text.lower() or 
                    any(query_lower in a.text.lower() for a in q.answers)]
    
    # Добавляем прогресс к каждому вопросу и применяем фильтры
    result = []
    for q in questions:
        progress = user_progress.get_question_progress(current_exam_name, q.id)
        
        # Фильтр по статусу
        if status_filter:
            if status_filter == 'not_attempted':
                # Непройденные - нет попыток
                if progress.get("attempts", 0) > 0:
                    continue
            elif status_filter == 'with_errors':
                # С ошибками - есть попытки, но есть неправильные ответы
                attempts = progress.get("attempts", 0)
                correct = progress.get("total_correct", 0)
                if attempts == 0 or attempts == correct:
                    continue
            elif status_filter == 'mastered':
                # Только усвоенные
                if not progress.get("mastered", False):
                    continue
        
        # Скрываем усвоенные если нужно (применяется после фильтра по статусу)
        if hide_mastered and progress.get("mastered", False) and status_filter != 'mastered':
            continue
        
        # Фильтр "усвоенные, не повторявшиеся более X дней"
        if not_repeated_days:
            try:
                days_threshold = float(not_repeated_days)
                if days_threshold >= 0:
                    # Только для усвоенных вопросов
                    if progress.get("mastered", False):
                        last_attempt = progress.get("last_attempt")
                        if last_attempt:
                            try:
                                last_attempt_date = datetime.fromisoformat(last_attempt)
                                days_since = (datetime.now() - last_attempt_date).total_seconds() / 86400
                                # Если повторяли недавно - пропускаем
                                if days_since < days_threshold:
                                    continue
                            except (ValueError, TypeError):
                                pass
                        # Если last_attempt отсутствует - включаем (давно не повторяли)
                    else:
                        # Не усвоенные вопросы - не включаем в этот фильтр
                        continue
            except ValueError:
                pass
        
        q_dict = q.to_dict()
        q_dict["progress"] = progress
        result.append(q_dict)
    
    return jsonify({
        "questions": result,
        "total": len(result)
    })


@app.route('/api/sections')
@require_auth
def get_sections():
    """Получение списка разделов"""
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    # Только вопросы с подтверждёнными ответами
    verified_questions = [q for q in question_bank.questions 
                         if q.exam_name == current_exam_name and q.is_verified]
    
    sections = {}
    for q in verified_questions:
        if q.section_number:
            if q.section_number not in sections:
                # Берём название секции напрямую из вопроса
                sections[q.section_number] = {
                    "number": q.section_number,
                    "name": q.section_name or f"Раздел {q.section_number}",
                    "count": 0
                }
            sections[q.section_number]["count"] += 1
    
    sections_list = sorted(sections.values(), key=lambda x: x["number"])
    return jsonify({"sections": sections_list})


@app.route('/api/question/<question_id>')
@require_auth
def get_question(question_id):
    """Получение конкретного вопроса"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    if not question.is_verified:
        return jsonify({"error": "Вопрос не имеет подтверждённого ответа"}), 400
    
    # Параметр show_answers позволяет показать правильные ответы (после проверки)
    show_answers = request.args.get('show_answers', 'false').lower() == 'true'
    
    q_dict = question.to_dict()
    q_dict["progress"] = user_progress.get_question_progress(current_exam_name, question_id)
    
    # Если не нужно показывать ответы, скрываем is_correct флаги
    if not show_answers:
        for answer in q_dict["answers"]:
            answer["is_correct"] = False
            answer["is_suggested"] = False
    
    return jsonify({"question": q_dict})


@app.route('/api/question/<question_id>/check', methods=['POST'])
@require_auth
def check_answer(question_id):
    """Проверка ответа пользователя"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    data = request.get_json()
    selected_answer_ids = data.get("selected_answers", [])
    dont_know = data.get("dont_know", False)
    
    # Находим правильные ответы
    correct_answer_ids = [a.id for a in question.answers if a.is_correct]
    
    if dont_know:
        # Пользователь не знает ответ
        is_correct = False
        progress = user_progress.update_question_progress(
            current_exam_name, question_id, is_correct=False, dont_know=True
        )
    else:
        # Проверяем ответ
        is_correct = set(selected_answer_ids) == set(correct_answer_ids)
        progress = user_progress.update_question_progress(
            current_exam_name, question_id, is_correct=is_correct, dont_know=False
        )
    
    return jsonify({
        "is_correct": is_correct,
        "correct_answers": correct_answer_ids,
        "progress": progress,
        "mastered": progress.get("mastered", False)
    })


@app.route('/api/question/<question_id>/mastered', methods=['POST'])
@require_auth
def set_question_mastered(question_id):
    """Установка/снятие отметки 'Усвоен'"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    question = question_bank.get_question_by_id(question_id)
    
    if not question:
        return jsonify({"error": "Вопрос не найден"}), 404
    
    data = request.get_json()
    mastered = data.get("mastered", False)
    
    progress = user_progress.set_mastered(current_exam_name, question_id, mastered)
    
    return jsonify({
        "success": True,
        "progress": progress
    })


@app.route('/api/statistics')
@require_auth
def get_statistics():
    """Получение статистики по экзамену"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    verified_questions = [q for q in question_bank.questions 
                         if q.exam_name == current_exam_name and q.is_verified]
    
    verified_ids = [q.id for q in verified_questions]
    
    stats = user_progress.get_exam_statistics(current_exam_name, verified_ids)
    section_stats = user_progress.get_section_statistics(current_exam_name, verified_questions)
    
    # Добавляем названия разделов (берём из вопросов)
    for section in section_stats:
        section_num = section["section_number"]
        # Находим вопрос с таким номером секции и берём из него название
        for q in verified_questions:
            if q.section_number == section_num and q.section_name:
                section["name"] = q.section_name
                break
        else:
            section["name"] = f"Раздел {section_num}"
    
    return jsonify({
        "overall": stats,
        "sections": section_stats
    })


@app.route('/api/session/start', methods=['POST'])
@require_auth
def start_session():
    """Начало сессии тестирования"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    data = request.get_json()
    question_ids = data.get("question_ids", [])
    
    if not question_ids:
        return jsonify({"error": "Не выбраны вопросы"}), 400
    
    # Проверяем, что все вопросы существуют и имеют подтверждённые ответы
    session_questions = []
    for q_id in question_ids:
        q = question_bank.get_question_by_id(q_id)
        if q and q.is_verified:
            q_dict = q.to_dict()
            q_dict["progress"] = user_progress.get_question_progress(current_exam_name, q_id)
            # Скрываем правильные ответы для режима тестирования
            for answer in q_dict["answers"]:
                answer["is_correct"] = False
                answer["is_suggested"] = False
            session_questions.append(q_dict)
    
    return jsonify({
        "success": True,
        "questions": session_questions,
        "total": len(session_questions)
    })


@app.route('/api/session/results', methods=['POST'])
@require_auth
def get_session_results():
    """Получение результатов сессии тестирования"""
    user_progress = get_current_user_progress()
    current_exam_name = get_current_exam_name()
    question_bank = get_question_bank(current_exam_name)
    
    data = request.get_json()
    answers = data.get("answers", {})  # {question_id: {selected: [], dont_know: bool}}
    
    results = []
    total_correct = 0
    total_answered = 0
    total_dont_know = 0
    
    for q_id, answer_data in answers.items():
        question = question_bank.get_question_by_id(q_id)
        if not question:
            continue
        
        selected = answer_data.get("selected", [])
        dont_know = answer_data.get("dont_know", False)
        
        correct_answer_ids = [a.id for a in question.answers if a.is_correct]
        
        if dont_know:
            is_correct = False
            total_dont_know += 1
            # Обновляем прогресс
            progress = user_progress.update_question_progress(
                current_exam_name, q_id, is_correct=False, dont_know=True
            )
        else:
            is_correct = set(selected) == set(correct_answer_ids)
            total_answered += 1
            if is_correct:
                total_correct += 1
            # Обновляем прогресс
            progress = user_progress.update_question_progress(
                current_exam_name, q_id, is_correct=is_correct, dont_know=False
            )
        
        # Формируем результат
        q_dict = question.to_dict()
        q_dict["progress"] = progress
        
        results.append({
            "question": q_dict,
            "selected_answers": selected,
            "correct_answers": correct_answer_ids,
            "is_correct": is_correct,
            "dont_know": dont_know,
            "progress": progress
        })
    
    return jsonify({
        "results": results,
        "summary": {
            "total_answered": total_answered,
            "total_correct": total_correct,
            "total_dont_know": total_dont_know,
            "accuracy": round(total_correct / total_answered * 100, 1) if total_answered > 0 else 0
        }
    })


@app.route('/api/health')
def health():
    """Диагностика: версия кода и список маршрутов"""
    routes = sorted([str(rule) for rule in app.url_map.iter_rules()])
    return jsonify({
        "status": "ok",
        "build": os.environ.get('BUILD_SHA', 'unknown'),
        "routes": routes
    })


if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs(SECRETS_DIR, exist_ok=True)
    
    # ВАЖНО: debug=True только для локальной разработки!
    # На продакшене (PythonAnywhere) debug отключен автоматически через WSGI
    is_development = os.environ.get('FLASK_ENV') == 'development' or not os.environ.get('SECRET_KEY')
    
    if is_development:
        logging.info("🔧 Режим разработки: debug=True, host=0.0.0.0")
        app.run(debug=True, host='0.0.0.0', port=5002)
    else:
        logging.info("🚀 Продакшен режим: debug=False")
        # В контейнере/при пробросе портов нужно слушать 0.0.0.0
        app.run(debug=False, host='0.0.0.0', port=5002)

