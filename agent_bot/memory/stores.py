"""Session and project memory management for conversational and task continuity."""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class MessageItem(BaseModel):
    role: str
    content: str
    timestamp: float = Field(default_factory=time.time)

class SessionStore:
    """Foydalanuvchilarning so'nggi suhbat tarixini tezkor RAM da saqlovchi xotira."""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self._sessions: Dict[int, List[MessageItem]] = {}

    def add_message(self, user_id: int, role: str, content: str):
        if user_id not in self._sessions:
            self._sessions[user_id] = []
        self._sessions[user_id].append(MessageItem(role=role, content=content))
        if len(self._sessions[user_id]) > self.max_history:
            self._sessions[user_id] = self._sessions[user_id][-self.max_history:]

    def get_history(self, user_id: int) -> List[MessageItem]:
        return self._sessions.get(user_id, [])

    def format_history_for_prompt(self, user_id: int) -> str:
        history = self.get_history(user_id)
        if not history:
            return ""
        lines = []
        for msg in history:
            prefix = "Foydalanuvchi:" if msg.role == "user" else "Agent:"
            lines.append(f"{prefix} {msg.content}")
        return "\n".join(lines)

    def clear(self, user_id: int):
        if user_id in self._sessions:
            del self._sessions[user_id]

    # --- MemoryStore bilan o'zaro moslik aliaslari ---
    def add(self, user_id: int, role: str, text: str) -> None:
        self.add_message(user_id, role, text)

    def history(self, user_id: int) -> List[MessageItem]:
        return self.get_history(user_id)

    def context_text(self, user_id: int, last_n: int = 6) -> str:
        history = self.get_history(user_id)[-last_n:]
        if not history:
            return ""
        return "Oldingi muloqot:\n" + "\n".join(
            f"{m.role.upper()}: {m.content}" for m in history
        )


class Project(BaseModel):
    project_id: str
    user_id: int
    title: str
    description: str
    version: int = 1
    requirements: List[str] = Field(default_factory=list)
    bom: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class ProjectStore:
    """Foydalanuvchi loyihasi va spetsifikatsiyasini diskda (JSON) uzoq muddat saqlash."""

    def __init__(self, data_dir: Path):
        self.projects_dir = data_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def save_project(self, project: Project) -> Path:
        project.updated_at = time.time()
        file_path = self.projects_dir / f"{project.project_id}.json"
        file_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        return file_path

    def load_project(self, project_id: str) -> Optional[Project]:
        file_path = self.projects_dir / f"{project_id}.json"
        if not file_path.exists():
            return None
        return Project.model_validate_json(file_path.read_text(encoding="utf-8"))

    def find_latest_project_for_user(self, user_id: int) -> Optional[Project]:
        latest_proj = None
        latest_time = 0.0
        for f in self.projects_dir.glob("*.json"):
            try:
                p = Project.model_validate_json(f.read_text(encoding="utf-8"))
                if p.user_id == user_id and p.updated_at > latest_time:
                    latest_proj = p
                    latest_time = p.updated_at
            except Exception:
                continue
        return latest_proj

    def create_project(self, user_id: int, title: str, description: str = "") -> Project:
        pid = f"proj_{user_id}_{int(time.time())}"
        proj = Project(
            project_id=pid,
            user_id=user_id,
            title=title,
            description=description
        )
        self.save_project(proj)
        return proj
