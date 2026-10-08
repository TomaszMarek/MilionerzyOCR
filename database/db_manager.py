import json
import os
import re
from typing import List, Set

from database.models import QuestionEntry


class DatabaseManager:
    def __init__(self, json_path: str = "milionerzy_baza.json", images_dir: str = "captures"):
        self.json_path = json_path
        self.images_dir = images_dir
        os.makedirs(self.images_dir, exist_ok=True)
        self.entries: List[QuestionEntry] = []
        self.load()

    def load(self):
        if not os.path.exists(self.json_path):
            self.entries = []
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.entries = [QuestionEntry.from_dict(item) for item in data if isinstance(item, dict)]
        except Exception:
            self.entries = []
        self.reindex_database()

    def reindex_database(self):
        if not self.entries:
            return
        needs_save = False
        seen_ids = set()
        for idx, entry in enumerate(self.entries, start=1):
            expected_id = f"{idx:03d}"
            if entry.id != expected_id or entry.id in seen_ids:
                entry.id = expected_id
                needs_save = True
            seen_ids.add(entry.id)
        if needs_save:
            self.save()

    def save(self):
        data = [e.to_dict() for e in self.entries]
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _delete_screenshot_file(entry: QuestionEntry):
        if entry and getattr(entry, "screenshot_path", None):
            path = entry.screenshot_path
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def add_entry(self, entry: QuestionEntry) -> bool:
        for e in self.entries:
            if (e.pytanie.strip().lower() == entry.pytanie.strip().lower() and
                    e.warianty == entry.warianty):
                return False
        max_id = 0
        for e in self.entries:
            nums = re.findall(r"\d+", str(e.id))
            if nums:
                val = int(nums[0])
                if val > max_id:
                    max_id = val

        entry.id = f"{max_id + 1:03d}"
        self.entries.append(entry)
        self.save()
        return True

    def update_entry(self, entry_id: str, new_pytanie: str, new_warianty: dict, new_poprawna: str,
                     new_station: str = "TVN"):
        for e in self.entries:
            if e.id == entry_id:
                e.pytanie = new_pytanie
                e.warianty = new_warianty
                e.poprawna_odpowiedz = new_poprawna
                e.station = new_station
                self.save()
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        for e in self.entries:
            if e.id == entry_id:
                self._delete_screenshot_file(e)
                break
        self.entries = [e for e in self.entries if e.id != entry_id]
        self.save()
        return True

    def delete_bulk(self, entry_ids: Set[str]) -> int:
        if not entry_ids:
            return 0
        deleted_count = 0
        remaining = []
        for e in self.entries:
            if e.id in entry_ids:
                self._delete_screenshot_file(e)
                deleted_count += 1
            else:
                remaining.append(e)
        self.entries = remaining
        self.save()
        return deleted_count

    def clear_all(self) -> int:
        count = len(self.entries)
        for e in self.entries:
            self._delete_screenshot_file(e)
        self.entries = []
        self.save()
        return count

    def get_all(self) -> List[QuestionEntry]:
        return self.entries

    def count(self) -> int:
        return len(self.entries)

    def toggle_favorite(self, entry_id: str) -> bool:
        for e in self.entries:
            if e.id == entry_id:
                e.is_favorite = not e.is_favorite
                self.save()
                return e.is_favorite
        return False