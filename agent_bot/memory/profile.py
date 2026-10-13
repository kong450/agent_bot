"""JARVIS user profile: doimiy shaxsiy xotira (ism, til, ovozli javob).

Saqlanadi: data/profiles/{user_id}.json — server qayta yonsa ham qoladi
(faqat kichik JSON, maxfiy narsa saqlanmaydi).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from agent_bot.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    user_id: int
    name: str = ""
    language: str = "uz"
    voice_out: bool = False  # inglizcha ovozli javob (Orpheus: faqat EN)


def _path(user_id: int) -> Path:
    d = Path(settings.data_dir) / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{user_id}.json"


def load_profile(user_id: int) -> UserProfile:
    p = _path(user_id)
    if not p.exists():
        return UserProfile(user_id=user_id)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return UserProfile(
            user_id=user_id,
            name=str(data.get("name", ""))[:60],
            language=str(data.get("language", "uz"))[:8],
            voice_out=bool(data.get("voice_out", False)),
        )
    except Exception:
        logger.warning("Profil o'qilmadi, default: %s", user_id)
        return UserProfile(user_id=user_id)


def save_profile(profile: UserProfile) -> None:
    try:
        _path(profile.user_id).write_text(
            json.dumps(asdict(profile), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Profil saqlanmadi")


def profile_line(profile: Optional[UserProfile]) -> str:
    """Promptga qo'shiladigan bir qatorli shaxs konteksti."""
    if profile is None or not profile.name:
        return ""
    return f"Foydalanuvchi ismi: {profile.name}."
