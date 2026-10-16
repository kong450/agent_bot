"""PytestLive marker ro'yxati.

`live` — jonli provayderga chiqadigan testlar (Groq/OpenRouter kvota sarflaydi,
tarmoqqa bog'liq). Tez lokal tekshiruv: pytest -m "not live"
To'liq tekshiruv: pytest
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "live: jonli API chaqiruvi (kvota sarflaydi)")
