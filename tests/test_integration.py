"""Integration acceptance tests for orchestrator, model router, and hardened sandbox."""
import pytest
from pathlib import Path
from agent_bot.config.settings import Settings
from agent_bot.core.orchestrator import MasterOrchestrator
from agent_bot.config.constants import IntentType
from agent_bot.tools.python_sandbox import PythonSandbox
from agent_bot.tools.file_reader import FileReader

@pytest.mark.live
@pytest.mark.asyncio
async def test_orchestrator_hardware_flow(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    orchestrator = MasterOrchestrator(settings)

    result = await orchestrator.process_user_message(
        user_id=12345,
        text="ESP32 mikrokontrolleriga 12V drayver mos keladimi?"
    )
    assert result.intent == IntentType.HARDWARE_COMPATIBILITY
    assert "APPARAT VA QURILMALAR MOSLIGI" in result.summary

@pytest.mark.asyncio
async def test_orchestrator_destruction_safety_gate(tmp_path: Path):
    settings = Settings(data_dir=tmp_path)
    orchestrator = MasterOrchestrator(settings)

    result = await orchestrator.process_user_message(
        user_id=12345,
        text="Mening barcha fayllarimni o'chirib tashla"
    )
    assert result.requires_approval is True
    assert "DESTRUKTIV AMAL ANIQLANDI" in result.summary

def test_hardened_sandbox_infinite_loop_timeout():
    # Cheksiz tsikl (while True) 2 soniyada to'xtatilishi kerak
    code = "while True:\n    pass"
    res = PythonSandbox.execute_code(code, timeout_seconds=2.0)
    assert res["success"] is False
    assert "VAQT CHEKLOVI" in res["output"]

def test_file_reader_txt(tmp_path: Path):
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Agent Bot test hujjati", encoding="utf-8")

    res = FileReader.read_file(txt_file)
    assert res["success"] is True
    assert "Agent Bot test hujjati" in res["text"]
