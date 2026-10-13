"""Test suite for intent classification and meta-prompt engine."""
import pytest
from agent_bot.config.constants import IntentType
from agent_bot.core.intent_classifier import IntentClassifier
from agent_bot.core.meta_prompt import MetaPromptEngine

def test_intent_classification():
    # Muhandislik hisobi
    intent, _, _ = IntentClassifier.classify("15 kVt quvvatli dvigatelning momentini hisobla")
    assert intent == IntentType.ENGINEERING_ANALYSIS

    # Uskunalar mosligi
    intent, _, _ = IntentClassifier.classify("ESP32 ga 12V motor drayver ulasam mos keladimi?")
    assert intent == IntentType.HARDWARE_COMPATIBILITY

    # Hujjat yaratish
    intent, _, _ = IntentClassifier.classify("Xarajatlar bo'yicha xlsx va docx hisobot yarat")
    assert intent == IntentType.DOCUMENT_GENERATION

    # Dasturlash
    intent, _, _ = IntentClassifier.classify("Ushbu Python kodidagi xatoni topib tuzat")
    assert intent == IntentType.SOFTWARE_DEVELOPMENT

def test_meta_prompt_building():
    prompt_data = MetaPromptEngine.build_execution_prompt(
        intent=IntentType.ENGINEERING_ANALYSIS,
        user_request="Elektr motor quvvatini hisobla",
        language="uz"
    )
    assert "SYSTEM ROLE:" in prompt_data["system_instruction"]
    assert "MECHANICAL & ELECTRICAL ENGINEERING" in prompt_data["system_instruction"]
    assert "[VAZIFA / MAQSAD]" in prompt_data["prompt"]
    assert "Elektr motor quvvatini hisobla" in prompt_data["prompt"]
