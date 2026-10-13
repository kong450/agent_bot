"""Test suite for tools (PythonSandbox, FileGenerator) and memory stores."""
from pathlib import Path
from agent_bot.tools.python_sandbox import PythonSandbox
from agent_bot.tools.file_generator import FileGenerator
from agent_bot.memory.stores import SessionStore, ProjectStore

def test_python_sandbox_calculation():
    code = "import math\nres = math.sqrt(144) * 2\nprint(f'RESULT={res}')"
    res = PythonSandbox.execute_code(code)
    assert res["success"] is True
    assert "RESULT=24.0" in res["output"]

def test_python_sandbox_security_blocking():
    code = "import os\nos.system('dir')"
    res = PythonSandbox.execute_code(code)
    assert res["success"] is False
    assert "XAVFSIZLIK CHEKLOVI" in res["output"]

def test_file_generator(tmp_path: Path):
    fg = FileGenerator(tmp_path)
    
    # Test Word
    docx_path = fg.generate_docx("Test Hisobot", [{"title": "Bo'lim 1", "content": "Tarkib"}])
    assert docx_path.exists()
    assert docx_path.suffix == ".docx"

    # Test Excel
    xlsx_path = fg.generate_xlsx("Smeta", ["Nomi", "Narxi"], [["Sensor", 25.0]])
    assert xlsx_path.exists()
    assert xlsx_path.suffix == ".xlsx"

    # Test PPTX
    pptx_path = fg.generate_pptx("Taqdimot", [{"title": "Slayd 1", "points": ["Band 1", "Band 2"]}])
    assert pptx_path.exists()
    assert pptx_path.suffix == ".pptx"

def test_session_and_project_memory(tmp_path: Path):
    # Session test
    session = SessionStore(max_history=2)
    session.add_message(101, "user", "Salom")
    session.add_message(101, "assistant", "Assalomu alaykum")
    session.add_message(101, "user", "Menga hisoblab ber")
    history = session.get_history(101)
    assert len(history) == 2
    assert history[0].content == "Assalomu alaykum"

    # Project test
    pstore = ProjectStore(tmp_path)
    proj = pstore.create_project(101, "IoT Dvigatel Loyihasi")
    proj.bom.append({"item": "ESP32", "qty": 1})
    pstore.save_project(proj)

    latest = pstore.find_latest_project_for_user(101)
    assert latest is not None
    assert latest.title == "IoT Dvigatel Loyihasi"
    assert len(latest.bom) == 1
