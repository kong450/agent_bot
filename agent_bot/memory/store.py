"""Per-user short-term memory (in-memory, bounded).

Strong agent needs context: what user asked before, what project is active.
Keeps last N turns per user (settings.max_history_length), builds compact
project_context string for MetaPromptEngine.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List

from agent_bot.config.settings import settings


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    text: str


@dataclass
class MemoryStore:
    max_turns: int = field(default_factory=lambda: settings.max_history_length * 2)
    max_users: int = 2000  # process-local leak himoyasi
    _data: Dict[int, Deque[Turn]] = field(default_factory=dict)

    def add(self, user_id: int, role: str, text: str) -> None:
        q = self._data.get(user_id)
        if q is None:
            if len(self._data) >= self.max_users:
                # Eng eski foydalanuvchini chiqarib tashlash (FIFO)
                oldest = next(iter(self._data))
                del self._data[oldest]
            q = deque(maxlen=self.max_turns)
            self._data[user_id] = q
        q.append(Turn(role=role, text=text[:2000]))

    def history(self, user_id: int) -> List[Turn]:
        return list(self._data.get(user_id, []))

    def context_text(self, user_id: int, last_n: int = 6) -> str:
        turns = self.history(user_id)[-last_n:]
        if not turns:
            return ""
        lines = [f"{t.role.upper()}: {t.text}" for t in turns]
        return "Oldingi muloqot:\n" + "\n".join(lines)

    def clear(self, user_id: int) -> None:
        self._data.pop(user_id, None)

    # --- SessionStore bilan o'zaro moslik aliaslari (canonical xotira API) ---
    def add_message(self, user_id: int, role: str, content: str) -> None:
        self.add(user_id, role, content)

    def get_history(self, user_id: int) -> List[Turn]:
        return self.history(user_id)

    def format_history_for_prompt(self, user_id: int) -> str:
        return self.context_text(user_id)


# Global instance used by handlers/orchestrator (simple, process-local)
memory = MemoryStore()
