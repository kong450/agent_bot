"""System-wide constants and enumerations for Agent Bot."""
from enum import Enum

class IntentType(str, Enum):
    """Foydalanuvchi murojaatining niyat turlari."""
    GENERAL_QUERY = "general_query"
    ENGINEERING_ANALYSIS = "engineering_analysis"
    HARDWARE_COMPATIBILITY = "hardware_compatibility"
    SCIENTIFIC_RESEARCH = "scientific_research"
    SCIENTIFIC_WRITING = "scientific_writing"
    PRODUCT_DEVELOPMENT = "product_development"
    BUSINESS_ANALYSIS = "business_analysis"
    DOCUMENT_GENERATION = "document_generation"
    SOFTWARE_DEVELOPMENT = "software_development"
    CONTINUE_PROJECT = "continue_project"

class VerificationLevel(str, Enum):
    """Hisob-kitob va ma'lumotning ishonchlilik darajasi."""
    VERIFIED = "VERIFIED"          # To'liq tekshirilgan va ishonchli manba/formula
    CALCULATED = "CALCULATED"      # Kod / Sandbox orqali hisoblangan
    ESTIMATED = "ESTIMATED"        # Taxminiy yoki bashoratli hisob

class CompatibilityVerdict(str, Enum):
    """Qurilmalar va detallarning o'zaro moslik xulosasi."""
    COMPATIBLE = "MOS"
    CONDITIONALLY_COMPATIBLE = "SHARTLI MOS"
    INCOMPATIBLE = "MOS EMAS"
    INSUFFICIENT_DATA = "MA'LUMOT YETARLI EMAS"
