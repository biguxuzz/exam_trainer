"""
Модуль для валидации данных Telegram Mini Apps
"""
import hmac
import hashlib
import base64
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
) -> Tuple[bool, Optional[Dict], str]:
    """
    Валидация initData от Telegram/MAX Mini App.

    Returns:
        Tuple[bool, Optional[Dict], str]: (успех, данные или None, причина отказа)
        Причины: ok | missing_init_data | missing_token | missing_hash |
                 auth_date_missing | auth_date_invalid | auth_date_future |
                 auth_date_expired | hash_mismatch
    """
    if not init_data:
        logger.warning(f"[{context}] Missing init_data")
        return False, None, "missing_init_data"

    if not bot_token:
        logger.error(f"[{context}] Missing bot_token!")
        return False, None, "missing_token"

    try:
        # Если MAX прислал весь фрагмент (WebAppData=...&WebAppPlatform=...)
        # вместо только значения WebAppData — извлекаем нужную часть
        if 'WebAppData=' in init_data and 'WebAppPlatform=' in init_data:
            fragment_params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
            extracted = fragment_params.get('WebAppData', '')
            if extracted:
                logger.info(f"[{context}] Extracted WebAppData from full fragment")
                init_data = extracted

        # Парсим query string
        params = parse_init_data(init_data)

        # Логируем ключи для диагностики
        param_keys = sorted(params.keys())
        logger.info(f"[{context}] initData keys: {param_keys}, token_prefix: {bot_token[:8]}...")

        # Проверяем наличие обязательных полей
        if 'hash' not in params:
            logger.warning(f"[{context}] Missing 'hash' field. Keys found: {param_keys}")
            return False, None, f"missing_hash (got keys: {param_keys})"

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
                    return False, None, f"auth_date_future (auth={auth_date}, now={current_time})"

                if age > max_age_seconds:
                    logger.warning(f"[{context}] init_data is too old: {age}s > {max_age_seconds}s")
                    return False, None, f"auth_date_expired ({age}s > {max_age_seconds}s)"
            except (ValueError, TypeError) as e:
                logger.warning(f"[{context}] Invalid auth_date value: {e}")
                return False, None, f"auth_date_invalid ({e})"
        else:
            logger.warning(f"[{context}] Missing auth_date in init_data")
            return False, None, "auth_date_missing"
        
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
            logger.warning(f"[{context}] Hash mismatch (method=raw_string)!")
            logger.warning(f"[{context}] Calculated FULL: {calculated_hash}")
            logger.warning(f"[{context}] Received  FULL: {received_hash}")
            logger.warning(f"[{context}] Full data_check_string:\n{data_check_string}")

            # Пробуем альтернативные варианты алгоритма (для отладки MAX)
            alt_methods = {}
            try:
                # Вариант 2: base64url-декодированный токен → байты
                tok_dec = base64.urlsafe_b64decode(bot_token + '==')
                sk2 = hmac.new(b"WebAppData", tok_dec, hashlib.sha256).digest()
                alt_methods['b64url_token'] = hmac.new(sk2, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
            except Exception:
                pass
            try:
                # Вариант 3: перестановка key/msg первого HMAC
                sk3 = hmac.new(bot_token.encode('utf-8'), b"WebAppData", hashlib.sha256).digest()
                alt_methods['swapped_key_msg'] = hmac.new(sk3, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
            except Exception:
                pass
            try:
                # Вариант 4: без промежуточного HMAC — прямо токен как ключ
                alt_methods['direct_token_key'] = hmac.new(bot_token.encode('utf-8'), data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
            except Exception:
                pass
            try:
                # Вариант 5: б64url-декодированный токен как прямой ключ
                tok_dec = base64.urlsafe_b64decode(bot_token + '==')
                alt_methods['direct_b64_key'] = hmac.new(tok_dec, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
            except Exception:
                pass

            matched = [name for name, h in alt_methods.items() if hmac.compare_digest(h, received_hash)]
            if matched:
                logger.warning(f"[{context}] ALTERNATIVE METHOD MATCHED: {matched}!")
            else:
                logger.warning(f"[{context}] No alternative matched. Alt prefixes: "
                               + ", ".join(f"{n}={h[:8]}" for n, h in alt_methods.items()))

            return False, None, (
                f"hash_mismatch (calc={calculated_hash[:8]}... recv={received_hash[:8]}..., "
                f"token={bot_token[:8]}..., alts_checked={list(alt_methods.keys())})"
            )

        # Парсим user если есть
        user_data = None
        if 'user' in params:
            try:
                user_data = json.loads(params['user'])
            except json.JSONDecodeError as e:
                logger.warning(f"[{context}] Failed to parse user data: {e}")

        # Возвращаем успех и распарсенные данные
        result = {
            'user': user_data,
            'auth_date': int(params['auth_date']),
            'query_id': params.get('query_id'),
            'start_param': params.get('start_param'),
            'chat_type': params.get('chat_type'),
            'chat_instance': params.get('chat_instance'),
        }

        return True, result, "ok"

    except Exception as e:
        logger.error(f"[{context}] Error verifying init_data: {e}", exc_info=True)
        return False, None, f"exception: {e}"
