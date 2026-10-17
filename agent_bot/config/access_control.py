"""Dynamic Access Control & Whitelist Manager for Agent Bot."""
import json
import logging
from pathlib import Path
from typing import Set

from agent_bot.config.settings import settings

logger = logging.getLogger(__name__)

# Asosiy admin ID lari (Shaxzod)
DEFAULT_ADMINS = {5528865108}

def _get_storage_path() -> Path:
    p = settings.data_dir / "allowed_users.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def load_allowed_users() -> Set[int]:
    """Baza va .env dan barcha ruxsat etilgan ID larni yuklash."""
    allowed: Set[int] = set(DEFAULT_ADMINS)
    if settings.allowed_telegram_ids:
        allowed.update(settings.allowed_telegram_ids)

    path = _get_storage_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    allowed.update(int(x) for x in data if str(x).isdigit())
        except Exception as e:
            logger.warning(f"allowed_users.json o'qishda xatolik: {e}")

    return allowed

def save_allowed_users(users: Set[int]) -> None:
    """Ruxsat berilgan ID larni saqlash."""
    path = _get_storage_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(users)), f, indent=2)
    except Exception as e:
        logger.error(f"allowed_users.json saqlashda xatolik: {e}")

# Xotiradagi kesh
_allowed_cache: Set[int] = load_allowed_users()

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish."""
    return user_id in DEFAULT_ADMINS or (settings.allowed_telegram_ids and user_id in settings.allowed_telegram_ids)

def is_allowed(user_id: int) -> bool:
    """Foydalanuvchiga botdan foydalanishga ruxsat bormi?"""
    global _allowed_cache
    if not _allowed_cache:
        _allowed_cache = load_allowed_users()
    return user_id in _allowed_cache

def allow_user(user_id: int) -> bool:
    """Yangi foydalanuvchiga ruxsat berish."""
    global _allowed_cache
    _allowed_cache.add(user_id)
    save_allowed_users(_allowed_cache)
    return True

def ban_user(user_id: int) -> bool:
    """Foydalanuvchidan ruxsatni bekor qilish (Adminni o'chirib bo'lmaydi)."""
    global _allowed_cache
    if user_id in DEFAULT_ADMINS:
        return False
    if user_id in _allowed_cache:
        _allowed_cache.remove(user_id)
        save_allowed_users(_allowed_cache)
    return True

def get_all_allowed() -> Set[int]:
    """Barcha ruxsat berilganlar ro'yxati."""
    global _allowed_cache
    return set(_allowed_cache)
