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
    
    Все поля кроме 'hash' сортируются по алфавиту
    и объединяются в строку формата: key=value\nkey=value\n...
    
    ВАЖНО: После Bot API 8.0+ может приходить поле 'signature', 
    но оно НЕ должно исключаться из data-check-string для проверки hash.
    Исключается только 'hash'.
    """
    # Исключаем только hash из проверки (signature должен быть включён!)
    filtered_params = {k: v for k, v in params.items() if k != 'hash'}
    
    # Сортируем по ключу
    sorted_params = sorted(filtered_params.items())
    
    # Формируем строку: key=value\nkey=value\n...
    return '\n'.join(f"{key}={value}" for key, value in sorted_params)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
    context: str = "Telegram"
) -> Tuple[bool, Optional[Dict]]:
    """
    Валидация initData от Telegram/MAX Mini App.
    
    Args:
        init_data: Query string из WebApp.initData
        bot_token: Токен бота
        max_age_seconds: Максимальный возраст данных в секундах (по умолчанию 24 часа)
        context: Метка для логов ("Telegram" или "MAX")
    
    Returns:
        Tuple[bool, Optional[Dict]]: (успех валидации, распарсенные данные или None)
    """
    if not init_data:
        logger.warning(f"[{context}] Missing init_data")
        return False, None
    
    if not bot_token:
        logger.error(f"[{context}] Missing bot_token!")
        return False, None
    
    try:
        # Парсим query string
        params = parse_init_data(init_data)
        
        # Логируем ключи для диагностики
        param_keys = sorted(params.keys())
        logger.info(f"[{context}] initData keys: {param_keys}, token_prefix: {bot_token[:8]}...")
        
        # Проверяем наличие обязательных полей
        if 'hash' not in params:
            logger.warning(f"[{context}] Missing 'hash' field in init_data. Keys found: {param_keys}")
            return False, None
        
        received_hash = params['hash']
        
        # Проверяем auth_date (свежесть данных)
        if 'auth_date' in params:
            try:
                auth_date = int(params['auth_date'])
                current_time = int(time.time())
                age = current_time - auth_date
                
                logger.info(f"[{context}] auth_date age: {age}s (limit: {max_age_seconds}s)")
                
                if age < 0:
                    logger.warning(f"[{context}] auth_date is in the future: {auth_date}, now: {current_time}")
                    return False, None
                
                if age > max_age_seconds:
                    logger.warning(f"[{context}] init_data is too old: {age}s > {max_age_seconds}s")
                    return False, None
            except (ValueError, TypeError) as e:
                logger.warning(f"[{context}] Invalid auth_date value: {e}")
                return False, None
        else:
            logger.warning(f"[{context}] Missing auth_date in init_data")
            return False, None
        
        # Строим data-check-string
        data_check_string = build_data_check_string(params)
        
        # Вычисляем secret_key = HMAC-SHA256(key="WebAppData", msg=bot_token)
        # ВАЖНО: key="WebAppData", msg=bot_token (согласно официальной документации Telegram)
        secret_key = hmac.new(
            b"WebAppData",
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
            logger.warning(f"[{context}] Hash mismatch!")
            logger.warning(f"[{context}] Calculated: {calculated_hash[:16]}... | Received: {received_hash[:16]}...")
            logger.warning(f"[{context}] token_prefix={bot_token[:8]}..., "
                           f"data_check_string (first 300): {data_check_string[:300]}")
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
