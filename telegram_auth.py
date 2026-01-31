"""
Модуль для валидации данных Telegram Mini Apps
"""
import hmac
import hashlib
import urllib.parse
import time
import json
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_init_data(query_string: str) -> Dict[str, str]:
    """Парсинг query string из Telegram.WebApp.initData"""
    return dict(urllib.parse.parse_qsl(query_string))


def build_data_check_string(params: Dict[str, str]) -> str:
    """
    Построение data-check-string для валидации.
    
    Все поля кроме 'hash' и 'signature' сортируются по алфавиту
    и объединяются в строку формата: key=value\nkey=value\n...
    """
    # Исключаем hash и signature из проверки
    filtered_params = {k: v for k, v in params.items() 
                      if k not in ('hash', 'signature')}
    
    # Сортируем по ключу
    sorted_params = sorted(filtered_params.items())
    
    # Формируем строку: key=value\nkey=value\n...
    return '\n'.join(f"{key}={value}" for key, value in sorted_params)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400
) -> Tuple[bool, Optional[Dict]]:
    """
    Валидация initData от Telegram Mini App.
    
    Args:
        init_data: Query string из Telegram.WebApp.initData
        bot_token: Токен бота от BotFather
        max_age_seconds: Максимальный возраст данных в секундах (по умолчанию 24 часа)
    
    Returns:
        Tuple[bool, Optional[Dict]]: (успех валидации, распарсенные данные или None)
    """
    if not init_data or not bot_token:
        logger.warning("Missing init_data or bot_token")
        return False, None
    
    try:
        # Парсим query string
        params = parse_init_data(init_data)
        
        # Проверяем наличие обязательных полей
        if 'hash' not in params:
            logger.warning("Missing hash in init_data")
            return False, None
        
        received_hash = params['hash']
        
        # Проверяем auth_date (свежесть данных)
        if 'auth_date' in params:
            try:
                auth_date = int(params['auth_date'])
                current_time = int(time.time())
                age = current_time - auth_date
                
                if age < 0:
                    logger.warning(f"auth_date is in the future: {auth_date}")
                    return False, None
                
                if age > max_age_seconds:
                    logger.warning(f"init_data is too old: {age} seconds")
                    return False, None
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid auth_date: {e}")
                return False, None
        else:
            logger.warning("Missing auth_date in init_data")
            return False, None
        
        # Строим data-check-string
        data_check_string = build_data_check_string(params)
        
        # Вычисляем secret_key = HMAC-SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            "WebAppData".encode('utf-8'),
            bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Вычисляем hash = HMAC-SHA256(data_check_string, secret_key)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Сравниваем хеши (защита от timing attacks)
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("Hash mismatch in init_data")
            return False, None
        
        # Парсим user если есть
        user_data = None
        if 'user' in params:
            try:
                user_data = json.loads(params['user'])
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse user data: {e}")
                # Продолжаем, user не обязателен для всех типов Mini Apps
        
        # Возвращаем успех и распарсенные данные
        result = {
            'user': user_data,
            'auth_date': int(params['auth_date']),
            'query_id': params.get('query_id'),
            'start_param': params.get('start_param'),
            'chat_type': params.get('chat_type'),
            'chat_instance': params.get('chat_instance'),
        }
        
        return True, result
        
    except Exception as e:
        logger.error(f"Error verifying init_data: {e}", exc_info=True)
        return False, None
