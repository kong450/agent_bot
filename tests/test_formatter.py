"""Test suite for TelegramFormatter ensuring all markdown is rendered cleanly in Telegram."""
from agent_bot.telegram.formatter import TelegramFormatter

def test_markdown_to_telegram_html_basic():
    md = "**Qalin matn** va *kursiv matn* hamda `inline_kod()`"
    html_res = TelegramFormatter.markdown_to_telegram_html(md)
    assert "<b>Qalin matn</b>" in html_res
    assert "<i>kursiv matn</i>" in html_res
    assert "<code>inline_kod()</code>" in html_res

def test_markdown_to_telegram_html_code_block():
    md = "Mana Python kodi:\n```python\ndef test():\n    return 5 > 3 & 2 < 4\n```"
    html_res = TelegramFormatter.markdown_to_telegram_html(md)
    assert '<pre><code class="language-python">' in html_res
    assert "&gt;" in html_res  # > belgisi to'g'ri escape qilingan
    assert "&amp;" in html_res # & belgisi to'g'ri escape qilingan

def test_markdown_to_telegram_html_tricky_characters():
    # Telegram MarkdownV2 buziladigan xavfli belgilar: ., _, *, -, (, ), [, ]
    md = "Tizim versiyasi: v1.0.0_beta-2 (ASUS TUF - RTX 4050 [16GB])"
    html_res = TelegramFormatter.markdown_to_telegram_html(md)
    # Hech qanday parse error keltirmasdan, butun holicha saqlanishi kerak
    assert "v1.0.0_beta-2 (ASUS TUF - RTX 4050 [16GB])" in html_res

def test_message_splitting():
    long_text = "Salom dunyo!\n" * 500
    chunks = TelegramFormatter.split_message(long_text, max_length=1000)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1000
