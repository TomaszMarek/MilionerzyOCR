from dataclasses import dataclass, asdict
from typing import Optional, Dict

@dataclass
class QuestionEntry:
    id: str
    pytanie: str
    warianty: Dict[str, str]
    poprawna_odpowiedz: Optional[str] = None
    screenshot_path: Optional[str] = None
    station: str = "TVN"
    is_favorite: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("id", ""),
            pytanie=data.get("pytanie", ""),
            warianty=data.get("warianty", {}),
            poprawna_odpowiedz=data.get("poprawna_odpowiedz"),
            screenshot_path=data.get("screenshot_path"),
            is_favorite=data.get("is_favorite", False),
            station=data.get("station", "TVN")
        )