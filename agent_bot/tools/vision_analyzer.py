"""Multimodal Vision Analyzer powered by Gemini 3.8 Flash for circuits, schemas, and diagrams."""
from pathlib import Path
from typing import Dict, Any, Optional
import base64
import logging

logger = logging.getLogger(__name__)

class VisionAnalyzer:
    """Rasmlar, elektronika platalari, skrinshotlar va chizmalarni ko'rib tahlil qiluvchi modul."""

    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client

    async def analyze_image(
        self,
        image_path: Path,
        user_prompt: str = "Ushbu tasvirni, undagi detallar, sxemalar yoki xatolarni chuqur tahlil qiling.",
        system_instruction: str = ""
    ) -> Dict[str, Any]:
        """Tasvirni Gemini 3.8 Flash multimodal orqali o'qib tahlil qiladi."""
        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": "Tasvir fayli topilmadi.", "text": ""}

        if not self.gemini_client:
            return {
                "success": False,
                "error": "Gemini 3.8 mijoz interfeysi mavjud emas.",
                "text": "Tasvir qabul qilindi, lekin Vision modeli ulanmagan."
            }

        try:
            from google.genai import types

            image_bytes = path.read_bytes()
            suffix = path.suffix.lower()
            mime_type = "image/jpeg"
            if suffix in [".png"]:
                mime_type = "image/png"
            elif suffix in [".webp"]:
                mime_type = "image/webp"

            prompt_parts = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                user_prompt
            ]

            config = {}
            if system_instruction:
                config["system_instruction"] = system_instruction

            response = self.gemini_client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt_parts,
                config=config
            )

            return {
                "success": True,
                "text": response.text.strip(),
                "model": "gemini-3.8-flash (Vision)"
            }

        except Exception as e:
            logger.error(f"Vision tahlili xatosi: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": f"Tasvirni tahlil qilishda xatolik yuz berdi: {str(e)}"
            }
