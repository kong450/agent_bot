"""Markdown (LLM plain-text output) -> Telegram HTML formatter.

Framework-agnostic: output HTML string, send with parse_mode="HTML"
in any library (aiogram, python-telegram-bot, pyrogram, raw Bot API).

Why HTML and not MarkdownV2:
- LLM writes standard Markdown (**bold**, # header, ```code```, [link](url), |table|).
- Telegram MarkdownV2 requires heavy escaping (_, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !)
  and still has no headers/tables support -> frequent "can't parse entities" errors.
- Telegram HTML supports only a small tag set, so we convert everything to that set
  and escape the rest. Result: any symbol renders formatted, never breaks sending.

Supported input (standard Markdown / plain text):
    # H1 .. ###### H6  -> <b>...</b>
    **bold**, __bold__ -> <b>
    *italic*, _italic_ -> <i>
    ~~strike~~        -> <s>
    ||spoiler||       -> <span class="tg-spoiler">
    `inline`          -> <code>
    ```lang\\ncode```  -> <pre><code class="language-lang">
    [text](https://..)-> <a href="..">
    > quote           -> <blockquote>
    - / * / • list    -> • list (plain, Telegram has no <ul>)
    1. numbered       -> kept as-is
    | table |         -> <pre> monospace block
    ---               -> ──────────
"""

from __future__ import annotations

import html
import re
from typing import List

TELEGRAM_LIMIT = 4096

# Placeholders for code blocks (must not collide with escaping)
_CODEBLOCK_PREFIX = "\x00CODEBLOCK"
_INLINECODE_PREFIX = "\x00INLINECODE"


def _extract_codeblocks(text: str, store: List[str]) -> str:
    """Replace ```...``` with placeholders, store finished HTML."""

    def _repl(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        # Strip single leading/trailing newline added by markdown fences
        code = code.strip("\n")
        escaped = html.escape(code, quote=False)
        if lang:
            lang_safe = re.sub(r"[^a-zA-Z0-9+\-#]", "", lang)
            store.append(
                f'<pre><code class="language-{lang_safe}">{escaped}</code></pre>'
            )
        else:
            store.append(f"<pre>{escaped}</pre>")
        return f"{_CODEBLOCK_PREFIX}{len(store) - 1}\x00"

    # ```lang\ncode```  (lang optional)
    return re.sub(r"```(\w[\w+\-#]*)?\n?(.*?)```", _repl, text, flags=re.DOTALL)


def _extract_inline_code(text: str, store: List[str]) -> str:
    """Replace `...` with placeholders, store finished HTML."""

    def _repl(m: re.Match) -> str:
        code = m.group(1)
        store.append(f"<code>{html.escape(code, quote=False)}</code>")
        return f"{_INLINECODE_PREFIX}{len(store) - 1}\x00"

    # single backtick only (triple already extracted)
    return re.sub(r"`([^`\n]+?)`", _repl, text)


def markdown_to_telegram_html(text: str) -> str:
    """Convert LLM Markdown plain-text to Telegram-safe HTML.

    Never raises on weird input. Always returns sendable HTML
    (with parse_mode="HTML").
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    codeblocks: List[str] = []
    inlinecodes: List[str] = []

    # 1. Pull out code first (do not touch inside)
    text = _extract_codeblocks(text, codeblocks)
    text = _extract_inline_code(text, inlinecodes)

    # 2. Escape everything else (&, <, >)
    text = html.escape(text, quote=False)

    # 3. Links: [text](url) — must run before bold/italic (brackets)
    def _link_repl(m: re.Match) -> str:
        label, url = m.group(1), m.group(2).strip()
        # Allow only safe protocols, else render as plain text
        if not re.match(r"^(https?://|tg://|mailto:)", url, re.IGNORECASE):
            return f"{label} ({url})"
        url_esc = html.escape(url, quote=True)
        return f'<a href="{url_esc}">{label}</a>'

    text = re.sub(r"\[([^\]\n]+?)\]\(([^)\s]+?)\)", _link_repl, text)

    # 4. Headers: # Text -> bold (Telegram HTML has no h1-h6)
    text = re.sub(
        r"(?m)^#{1,6}\s+(.+?)\s*$",
        lambda m: f"<b>{m.group(1).strip()}</b>",
        text,
    )

    # 5. Blockquote: &gt; (escaped >) at line start -> <blockquote>
    # Merge consecutive quote lines into one blockquote
    lines = text.split("\n")
    out_lines: List[str] = []
    quote_buf: List[str] = []
    for ln in lines:
        q = re.match(r"^(?:&gt;\s?)+", ln)
        if q:
            quote_buf.append(ln[q.end():])
        else:
            if quote_buf:
                out_lines.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")
                quote_buf = []
            out_lines.append(ln)
    if quote_buf:
        out_lines.append("<blockquote>" + "\n".join(quote_buf) + "</blockquote>")
    text = "\n".join(out_lines)

    # 6. Horizontal rule -> separator line
    text = re.sub(r"(?m)^\s*(---|\*\*\*|___)\s*$", "──────────", text)

    # 7. Tables: any consecutive block with '|' (2+ lines) -> <pre> block
    # Markdown separator row (|---|---|) is dropped.
    lines = text.split("\n")
    out_lines = []
    tbl_buf: List[str] = []
    sep_re = re.compile(r"^\s*\|?[\s:|\-]+(\|[\s:|\-]+)*\|?\s*$")

    def _flush_table() -> None:
        if not tbl_buf:
            return
        # drop separator rows like |---|---|
        rows = [r for r in tbl_buf if not (sep_re.match(r) and "-" in r)]
        # strip leading/trailing pipe for cleaner monospace view
        cleaned = [re.sub(r"^\s*\|\s?", "", re.sub(r"\s?\|\s*$", "", r)) for r in rows]
        out_lines.append("<pre>" + "\n".join(cleaned) + "</pre>")

    for ln in lines:
        if "|" in ln and ln.count("|") >= 1:
            # heuristic: previous/next line also table-like, or line looks like row
            tbl_buf.append(ln)
        else:
            if len(tbl_buf) >= 2:
                _flush_table()
            elif tbl_buf:
                out_lines.extend(tbl_buf)
            tbl_buf = []
            out_lines.append(ln)
    if len(tbl_buf) >= 2:
        _flush_table()
    elif tbl_buf:
        out_lines.extend(tbl_buf)
    text = "\n".join(out_lines)

    # 8. Lists: "- item" / "* item" -> "• item" (avoid clash with italic/bold)
    text = re.sub(r"(?m)^\s*[-•]\s+", "• ", text)
    # "* item" only when used as list marker at line start
    text = re.sub(r"(?m)^\s*\*\s+", "• ", text)

    # 9. Bold: **text** and __text__
    text = re.sub(r"\*\*([^*`\n]+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_`\n]+?)__", r"<b>\1</b>", text)

    # 10. Strikethrough: ~~text~~
    text = re.sub(r"~~([^~`\n]+?)~~", r"<s>\1</s>", text)

    # 11. Spoiler: ||text||
    text = re.sub(r"\|\|([^|\n]+?)\|\|", r'<span class="tg-spoiler">\1</span>', text)

    # 12. Italic: *text* and _text_ (after bold, avoid list markers and inside words)
    text = re.sub(r"(?<!\w)\*([^*\n`]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n`]+?)_(?!\w)", r"<i>\1</i>", text)

    # 13. Restore inline code + codeblocks
    for i, h in enumerate(inlinecodes):
        text = text.replace(f"{_INLINECODE_PREFIX}{i}\x00", h)
    for i, h in enumerate(codeblocks):
        text = text.replace(f"{_CODEBLOCK_PREFIX}{i}\x00", h)

    # 14. Safety: strip any tag not allowed by Telegram (keep content)
    # Allowed: b strong i em u ins s strike del code pre a blockquote span
    text = re.sub(
        r"</?(?!b\b|strong\b|i\b|em\b|u\b|ins\b|s\b|strike\b|del\b"
        r"|code\b|pre\b|a\b|blockquote\b|expandable_blockquote\b|span\b)[a-zA-Z][^>]*>",
        "",
        text,
    )

    return text.strip()


def to_plain_text(markdown_text: str) -> str:
    """Strip Markdown to clean plain text (fallback when HTML send fails).

    Use when parse_mode="HTML" returns Bad Request: send this with
    parse_mode=None instead.
    """
    if not markdown_text:
        return ""
    t = markdown_text.replace("\r\n", "\n")
    # code fences -> keep code only
    t = re.sub(r"```\w*\n?(.*?)```", r"\1", t, flags=re.DOTALL)
    t = re.sub(r"`([^`]+?)`", r"\1", t)
    # images ![a](u) -> a
    t = re.sub(r"!\[([^\]]*?)\]\([^)]+?\)", r"\1", t)
    # links [a](u) -> a (u)
    t = re.sub(r"\[([^\]]+?)\]\(([^)]+?)\)", r"\1 (\2)", t)
    # headers, quotes, lists, bold/italic/strike/spoiler markers
    t = re.sub(r"(?m)^#{1,6}\s+", "", t)
    t = re.sub(r"(?m)^\s*&gt;\s?", "", t)
    t = re.sub(r"(?m)^\s*>\s?", "", t)
    t = re.sub(r"\*\*([^*]+?)\*\*", r"\1", t)
    t = re.sub(r"__([^_]+?)__", r"\1", t)
    t = re.sub(r"~~([^~]+?)~~", r"\1", t)
    t = re.sub(r"\|\|([^|]+?)\|\|", r"\1", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"\1", t)
    # unescape html entities if any
    t = html.unescape(t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def split_html_message(text_html: str, limit: int = TELEGRAM_LIMIT) -> List[str]:
    """Split HTML message into <=limit chunks on line boundaries.

    Does not split inside <pre>...</pre> blocks unless a single block
    itself exceeds the limit (then hard-split with tags reopened).
    """
    if len(text_html) <= limit:
        return [text_html]

    # Split by <pre> blocks to keep them intact
    parts = re.split(r"(<pre>.*?</pre>)", text_html, flags=re.DOTALL)
    chunks: List[str] = []
    current = ""

    for part in parts:
        if not part:
            continue
        if part.startswith("<pre>") and len(part) > limit:
            # Oversized code block: qator chegarasida bo'lib, teglarni qayta ochish.
            # inner allaqachon escape qilingan — qayta escape QILINMAYDI (double-escape bo'lmasligi uchun).
            inner = re.sub(r"^<pre>|</pre>$", "", part)
            if current:
                chunks.append(current.rstrip())
                current = ""
            buf = ""
            for line in inner.split("\n"):
                if len(buf) + len(line) + 1 > limit - 11 and buf:
                    chunks.append(f"<pre>{buf}</pre>")
                    buf = ""
                buf = f"{buf}\n{line}" if buf else line
                while len(buf) > limit - 11:
                    # Juda uzun yakka qator: bo'shliq chegarasida kesish
                    cut = buf.rfind(" ", 0, limit - 11)
                    if cut <= 0:
                        cut = limit - 11
                    chunks.append(f"<pre>{buf[:cut]}</pre>")
                    buf = buf[cut:].lstrip()
            if buf:
                chunks.append(f"<pre>{buf}</pre>")
            continue
        if len(current) + len(part) + 1 > limit:
            if current:
                chunks.append(current.rstrip())
            current = part
            # part itself may still be > limit (long paragraph) -> split by lines
            while len(current) > limit:
                cut = current.rfind("\n", 0, limit)
                if cut <= 0:
                    cut = limit
                chunks.append(current[:cut].rstrip())
                current = current[cut:].lstrip("\n")
        else:
            current = f"{current}\n{part}" if current else part

    if current.strip():
        chunks.append(current.rstrip())

    # Final safety: any chunk still too long -> chegarada kesish (teg o'rtasidan emas)
    def _safe_cut(s: str, lim: int) -> int:
        cut = s.rfind("\n", 0, lim)
        if cut <= 0:
            cut = s.rfind(" ", 0, lim)
        if cut <= 0:
            cut = lim
        # Teg o'rtasida kesilmaslik: oxirgi '<' yopilmagan bo'lsa, undan oldin kesish
        lt = s.rfind("<", 0, cut)
        gt = s.rfind(">", 0, cut)
        if lt > gt:
            cut = lt
            if cut <= 0:
                cut = lim
        return cut

    final: List[str] = []
    for c in chunks:
        while len(c) > limit:
            cut = _safe_cut(c, limit)
            final.append(c[:cut].rstrip() or c[:limit])
            c = c[cut:].lstrip("\n")
            if not c:
                break
        if c:
            final.append(c)
    return final
