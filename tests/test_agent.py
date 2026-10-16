"""Strong-agent verification: calculator, memory, orchestrator, formatting."""
import pytest

from agent_bot.agents.orchestrator import AgentOrchestrator, extract_verdict, _run_calc_blocks
from agent_bot.config.constants import CompatibilityVerdict, IntentType
from agent_bot.config.settings import Settings
from agent_bot.core.intent_classifier import IntentClassifier
from agent_bot.core.llm_client import MockLLMClient
from agent_bot.memory.store import MemoryStore
from agent_bot.telegram.formatter import TelegramFormatter
from agent_bot.telegram.formatting import markdown_to_telegram_html
from agent_bot.tools.calculator import safe_calculate
from agent_bot.tools.python_sandbox import PythonSandbox


def test_safe_calculator():
    assert safe_calculate("2 + 3*4").value == 14
    assert safe_calculate("sqrt(16) + pi").value > 7
    with pytest.raises(ValueError):
        safe_calculate("__import__('os').system('x')")
    with pytest.raises(ValueError):
        safe_calculate("open('f').read()")


def test_memory_context():
    m = MemoryStore(max_turns=4)
    m.add(1, "user", "salom")
    m.add(1, "assistant", "alik")
    assert "salom" in m.context_text(1)
    m.clear(1)
    assert m.context_text(1) == ""


def test_verdict_extract():
    assert extract_verdict("xulosa: [MOS EMAS]") == CompatibilityVerdict.INCOMPATIBLE
    assert extract_verdict("[SHARTLI MOS] kerak") == CompatibilityVerdict.CONDITIONALLY_COMPATIBLE
    assert extract_verdict("oddiy matn") is None


@pytest.mark.asyncio
async def test_orchestrator_end_to_end_mock():
    orch = AgentOrchestrator(llm=MockLLMClient(), store=MemoryStore())
    res = await orch.handle(42, "ESP32 ga 12V motor drayver ulasam mos keladimi?")
    assert res.intent == IntentType.HARDWARE_COMPATIBILITY
    assert res.raw_answer and res.html and res.chunks
    # HTML telegramda yuboriladigan holatda bo'lishi kerak
    assert "<b>" in res.html or "<code>" in res.html or "<pre>" in res.html
    # Mock javob buzmasdan formatlanishi kerak
    assert markdown_to_telegram_html(res.raw_answer) == res.html


def test_classifier_word_boundaries():
    # 'hisobot' endi muhandislikka tortilmasligi kerak (regressiya testi)
    intent, _, _ = IntentClassifier.classify("Xarajatlar bo'yicha xlsx va docx hisobot yarat")
    assert intent == IntentType.DOCUMENT_GENERATION
    # 'mos' yakka so'zi hardware, lekin 'cosmos' kabi so'z ichida ishlamasligi kerak
    intent, _, _ = IntentClassifier.classify("cosmos haqida gapir")
    assert intent == IntentType.GENERAL_QUERY


def test_settings_ids_parsing():
    s = Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_TELEGRAM_IDS="123, 456")
    assert s.allowed_telegram_ids == [123, 456]
    assert s.is_user_allowed(123) is True
    assert s.is_user_allowed(999) is False
    s2 = Settings(TELEGRAM_BOT_TOKEN="x", ALLOWED_TELEGRAM_IDS="")
    assert s2.is_user_allowed(999) is True  # bo'sh = ochiq bot


def test_sandbox_bypass_blocked():
    for evil in [
        "__import__('os')",
        "getattr(math, 'sqrt')",
        "(1).__class__",
        "open('f')",
        "eval('1+1')",
    ]:
        res = PythonSandbox.execute_code(evil)
        assert res["success"] is False
        assert "XAVFSIZLIK" in res["output"]


def test_calc_block_verification():
    raw = "Natija:\n```calc\nprint(6*7)\n```"
    new_raw, outputs = _run_calc_blocks(raw)
    assert outputs and "42" in outputs[0]
    assert "[CALCULATED]" in new_raw


def test_formatter_facade_delegates():
    md = "**Qalin** va *kursiv* hamda `kod()`"
    assert TelegramFormatter.markdown_to_telegram_html(md) == markdown_to_telegram_html(md)
    chunks = TelegramFormatter.split_message("a\n" * 3000, max_length=1000)
    assert len(chunks) > 1 and all(len(c) <= 1000 for c in chunks)


@pytest.mark.asyncio
async def test_model_router_fallback_chain():
    from agent_bot.agents.orchestrator import _call_llm
    from agent_bot.core.llm_client import BaseLLMClient, LLMResponse

    class _FailClient(BaseLLMClient):
        async def generate(self, system_instruction: str, prompt: str) -> LLMResponse:
            raise RuntimeError("ataylab yiqitildi")

    # Adapter eski interfeysni normallaydi
    text, model = await _call_llm(MockLLMClient(), "sys", "hello")
    assert text and model == "mock-1"
    # Yiqilgan clientda xato ko'tariladi (router buni ushlab keyingisiga o'tadi)
    with pytest.raises(RuntimeError):
        await _call_llm(_FailClient(), "sys", "hello")


@pytest.mark.asyncio
async def test_destructive_gate_blocks_then_forces():
    from agent_bot.agents.orchestrator import is_destructive

    assert is_destructive("barcha fayllarimni o'chir") is True
    assert is_destructive("salom, kuchlanish qancha?") is False

    orch = AgentOrchestrator(llm=MockLLMClient(), store=MemoryStore())
    blocked = await orch.handle(7, "barcha fayllarimni o'chir")
    assert blocked.needs_confirmation is True
    assert blocked.chunks
    forced = await orch.handle(7, "barcha fayllarimni o'chir", force=True)
    assert forced.needs_confirmation is False


@pytest.mark.asyncio
async def test_deep_mode_parallel():
    orch = AgentOrchestrator(llm=MockLLMClient(), store=MemoryStore())
    res = await orch.handle(
        9,
        "15 kVt dvigatel uchun reduktor tanlash kerak va samaradorlikni hisobla, qaysi variant arzon?",
    )
    assert res.deep_mode is True
    assert "Muqobil" in res.raw_answer


@pytest.mark.asyncio
async def test_document_file_generation(tmp_path=None):
    orch = AgentOrchestrator(llm=MockLLMClient(), store=MemoryStore())
    res = await orch.handle(11, "smeta bo'yicha xlsx hisobot yarat")
    assert res.intent == IntentType.DOCUMENT_GENERATION
    assert res.files and res.files[0].endswith(".xlsx")


def test_single_brain_wiring():
    """main.py handlers'dagi YAGONA orchestrator instance'ni ishlatishi kerak."""
    import main as bot_main
    from agent_bot.telegram import handlers

    assert bot_main.orchestrator is handlers.orchestrator


def test_openai_compat_client_defaults():
    """Yagona HTTP mijoz settings maydonlari bilan initsializatsiya bo'ladi."""
    from agent_bot.core.openai_client import OpenAICompatClient

    c = OpenAICompatClient(api_key="x")
    assert c.base_url == "https://api.openai.com/v1"
    assert c.model
    c2 = OpenAICompatClient(
        api_key="y",
        base_url="https://openrouter.ai/api/v1",
        model="openrouter/free",
        extra_headers={"HTTP-Referer": "https://github.com/agent-bot"},
    )
    assert c2.extra_headers["HTTP-Referer"].startswith("https://")


def test_tts_chunking():
    from agent_bot.tools.voice import split_for_tts

    assert split_for_tts("") == []
    chunks = split_for_tts("Salom. Bu uzun test jumlasi. " * 20)
    assert len(chunks) > 1 and all(len(c) <= 200 for c in chunks)
    assert " ".join(chunks).replace("  ", " ").strip() != ""


def test_voice_in_kept_tts_out_removed():
    """Ovozli kirish (STT) qoladi, ovozli javob (TTS) butunlay o'chirilgan."""
    import agent_bot.telegram.handlers as handlers

    assert hasattr(handlers, "on_voice")  # kirish: tushunish saqlangan
    assert not hasattr(handlers, "should_voice_reply")  # qoida o'chirilgan
    assert not hasattr(handlers, "cmd_voice_toggle")  # /ovoz buyrug'i o'chirilgan


def test_profile_line():
    from agent_bot.memory.profile import UserProfile, profile_line

    assert profile_line(UserProfile(user_id=1, name="Alisher")) == "Foydalanuvchi ismi: Alisher."
    assert profile_line(UserProfile(user_id=1)) == ""
    assert profile_line(None) == ""


@pytest.mark.asyncio
async def test_voice_needs_key():
    from agent_bot.tools import voice as voice_mod

    if not voice_mod.settings.groq_api_key:
        with pytest.raises(RuntimeError):
            await voice_mod.transcribe_voice(b"fake-audio")


def test_ai_mode_support():
    from agent_bot.memory.profile import UserProfile, save_profile, load_profile
    from agent_bot.agents.orchestrator import AgentOrchestrator
    from agent_bot.config.constants import IntentType

    prof = UserProfile(user_id=99999, name="TestUser", ai_mode="fast")
    save_profile(prof)
    loaded = load_profile(99999)
    assert loaded.ai_mode == "fast"

    orch = AgentOrchestrator()
    assert orch._resolve_model_pref(99999, IntentType.GENERAL_QUERY, "salom") == "fast"

    prof.ai_mode = "gpt6"
    save_profile(prof)
    assert orch._resolve_model_pref(99999, IntentType.GENERAL_QUERY, "salom") == "gpt6"


def test_claude_headers_and_parse():
    from agent_bot.core.anthropic_client import build_headers, parse_content

    h = build_headers("k")
    assert h["x-api-key"] == "k" and h["anthropic-version"] == "2023-06-01"
    data = {"content": [{"type": "text", "text": "salom"}, {"type": "tool_use"}]}
    assert parse_content(data) == "salom"
    with pytest.raises(ValueError):
        parse_content({"content": []})


def test_claude_needs_key():
    import agent_bot.core.anthropic_client as ac
    from agent_bot.core.anthropic_client import AnthropicClient

    if not ac.settings.anthropic_api_key:
        with pytest.raises(RuntimeError):
            AnthropicClient(api_key=None)
    else:
        assert AnthropicClient().model

