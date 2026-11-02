"""
Translation Manager for Rosario + Vampire PS2 Translation Pipeline.
Maintains the JSON translation schema and provides utilities for translators and patchers.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

DEFAULT_GAME_TITLE = "Rosario + Vampire PS2"
DEFAULT_SCHEMA_VERSION = "1.0"
DEFAULT_LANGUAGES = ["en", "es", "fr"]


class TranslationString:
    def __init__(
        self,
        string_id: str,
        source_file: str,
        offset_hex: str,
        original_ja: str,
        translations: Optional[Dict[str, str]] = None,
        context: str = ""
    ):
        self.id = string_id
        self.source_file = source_file
        self.offset_hex = offset_hex
        self.original_ja = original_ja
        self.translations: Dict[str, str] = translations if translations is not None else {lang: "" for lang in DEFAULT_LANGUAGES}
        self.context = context

    def to_dict(self, include_original: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "source_file": self.source_file,
            "offset_hex": self.offset_hex,
        }
        if include_original:
            d["original_ja"] = self.original_ja
        d["translations"] = self.translations
        d["context"] = self.context
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TranslationString":
        return cls(
            string_id=d["id"],
            source_file=d["source_file"],
            offset_hex=d["offset_hex"],
            original_ja=d.get("original_ja", ""),
            translations=d.get("translations", {}),
            context=d.get("context", "")
        )


class TranslationProject:
    def __init__(self, game_title: str = DEFAULT_GAME_TITLE, version: str = DEFAULT_SCHEMA_VERSION):
        self.game_title = game_title
        self.version = version
        self.strings: List[TranslationString] = []

    def add_string(
        self,
        string_id: str,
        source_file: str,
        offset_hex: str,
        original_ja: str,
        translations: Optional[Dict[str, str]] = None,
        context: str = ""
    ) -> TranslationString:
        ts = TranslationString(string_id, source_file, offset_hex, original_ja, translations, context)
        self.strings.append(ts)
        return ts

    def save(self, json_path: Path | str, include_original: bool = True, only_translated: bool = False):
        json_path = Path(json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        items = self.strings
        if only_translated:
            items = [s for s in items if any(v.strip() for v in s.translations.values())]
        payload = {
            "game_title": self.game_title,
            "version": self.version,
            "strings": [s.to_dict(include_original=include_original) for s in items]
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, json_path: Path | str) -> "TranslationProject":
        json_path = Path(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        proj = cls(
            game_title=data.get("game_title", DEFAULT_GAME_TITLE),
            version=data.get("version", DEFAULT_SCHEMA_VERSION)
        )
        for d in data.get("strings", []):
            proj.strings.append(TranslationString.from_dict(d))
        return proj

    def get_available_languages(self) -> List[str]:
        langs = set()
        for s in self.strings:
            langs.update(s.translations.keys())
        return sorted(list(langs))

    def get_progress(self) -> Dict[str, Dict[str, Any]]:
        """
        Returns translation statistics per language:
        total strings, translated count, and percentage completed.
        """
        total = len(self.strings)
        langs = self.get_available_languages()
        stats = {}
        for l in langs:
            translated = sum(1 for s in self.strings if s.translations.get(l, "").strip())
            pct = (translated / total * 100.0) if total > 0 else 0.0
            stats[l] = {
                "total": total,
                "translated": translated,
                "percentage": round(pct, 2)
            }
        return stats
