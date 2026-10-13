"""Interactive Inline Keyboards for human approvals and multi-option branching."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_approval_keyboard(approval_id: str) -> InlineKeyboardMarkup:
    """Destruktiv yoki muhim amallar uchun tasdiqlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data=f"approve:{approval_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject:{approval_id}")
            ]
        ]
    )

def get_multi_option_keyboard() -> InlineKeyboardMarkup:
    """Master Prompt V3 dagi A/B/C variantlarni bir tugma bilan tanlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Minimal variant", callback_data="opt:minimal"),
                InlineKeyboardButton(text="2️⃣ Optimal variant", callback_data="opt:optimal"),
                InlineKeyboardButton(text="3️⃣ Ilg'or variant", callback_data="opt:advanced"),
            ],
            [
                InlineKeyboardButton(text="📊 Grafik chizish", callback_data="act:chart"),
                InlineKeyboardButton(text="📎 Hujjatga chiqarish", callback_data="act:export_doc"),
            ]
        ]
    )
