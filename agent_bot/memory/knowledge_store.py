"""Long-term Episodic User Knowledge Store (JARVIS Persona & Continuity Memory)."""
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class UserFact(BaseModel):
    category: str  # masalan: "hardware", "project", "car", "preference"
    fact: str
    updated_at: float = Field(default_factory=time.time)

class UserProfile(BaseModel):
    user_id: int
    name: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    known_facts: List[UserFact] = Field(default_factory=list)
    total_interactions: int = 0
    updated_at: float = Field(default_factory=time.time)

class UserKnowledgeStore:
    """Foydalanuvchi haqidagi uzoq muddatli shaxsiy ma'lumotlar va preferensiyalar ombori."""

    def __init__(self, data_dir: Path):
        self.profiles_dir = data_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, user_id: int) -> Path:
        return self.profiles_dir / f"user_{user_id}.json"

    def get_or_create_profile(self, user_id: int) -> UserProfile:
        path = self._get_path(user_id)
        if path.exists():
            try:
                return UserProfile.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        profile = UserProfile(user_id=user_id)
        self.save_profile(profile)
        return profile

    def save_profile(self, profile: UserProfile):
        profile.updated_at = time.time()
        path = self._get_path(profile.user_id)
        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    def add_fact(self, user_id: int, category: str, fact: str):
        profile = self.get_or_create_profile(user_id)
        # Mavjud faktlarni takrorlamaslik
        for f in profile.known_facts:
            if f.category == category and f.fact.lower() == fact.lower():
                return
        profile.known_facts.append(UserFact(category=category, fact=fact))
        profile.total_interactions += 1
        self.save_profile(profile)

    def format_user_context(self, user_id: int) -> str:
        """Prompt ichiga qo'shish uchun foydalanuvchi shaxsiy bilimlarining qisqacha xulosasi."""
        profile = self.get_or_create_profile(user_id)
        if not profile.known_facts:
            return ""

        facts_str = "\n".join(f"- [{f.category.upper()}] {f.fact}" for f in profile.known_facts[-8:])
        return f"[FOYDALANUVCHI HAQIDA BILIMLAR / SHAXSIY KONTEKST]:\n{facts_str}"
