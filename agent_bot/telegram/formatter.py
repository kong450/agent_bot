"""TelegramFormatter — canonical formatting core'ga yupqa wrapper.

Barcha konversiya mantiqi yagona joyda: agent_bot.telegram.formatting.
Bu klass faqat backward-compat uchun saqlanadi (eski testlar/handlerlar
TelegramFormatter API'sini ishlatadi). Yangi kod to'g'ridan-to'g'ri
formatting.markdown_to_telegram_html ni ishlatsin.
"""
from typing import List

from agent_bot.telegram.formatting import (
    markdown_to_telegram_html as _core_html,
    split_html_message as _core_split,
    to_plain_text as _core_plain,
)


class TelegramFormatter:
    """Yagona formatting dvigateliga delegatsiya qiluvchi facade."""

    @classmethod
    def markdown_to_telegram_html(cls, text: str) -> str:
        return _core_html(text)

    @classmethod
    def to_plain_text(cls, text: str) -> str:
        return _core_plain(text)

    @classmethod
    def split_message(cls, text: str, max_length: int = 4000) -> List[str]:
        # Eski chaqiruvchilar max_length=4000 beradi; core limiti 4096.
        return _core_split(text, limit=min(max_length, 4096))
