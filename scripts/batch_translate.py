"""
Batch translation script for Rosario + Vampire Capu 2 (PS2).
Translates untranslated dialogue lines in extracted_text/strings_dialogue.json
and syncs them to translations/strings_dialogue.json.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict

import requests

sys.path.insert(0, "scripts")
from font_mapper import wrap_english_text

JP_NORMALIZATIONS = {
    "デヮ": "デレ",
    "姿我": "怪我",
    "プリイド": "プライド",
    "フロート": "フルート",
    "トリイアングロ": "トライアングル",
    "リイブ": "ライブ",
    "プワデューサー": "プロデューサー",
    "シンプロ": "シンプル",
    "トンネロ": "トンネル",
    "目笛地": "目的地",
    "開放笛": "開放的",
    "テヮビ": "テレビ",
    "環字": "漢字",
    "熱討": "鉄槌",
    "作極": "作曲",
    "能書": "能書き",
    "ヮベロ": "レベル",
    "スパロタ": "スパルタ",
    "無謎": "無難",
    "プヮッシャー": "プレッシャー",
    "水着恥": "水着姿",
    "素的": "素敵",
    "勘い": "鈍い",
}

NAME_REPLACEMENTS = [
    (r"\bTsukine\b", "Tsukune"),
    (r"\bMoeka\b", "Moka"),
    (r"\bMurasaki-chan\b", "Yukari-chan"),
    (r"\bMurasaki\b", "Yukari"),
    (r"\bMidorihime\b", "Ruby"),
    (r"\bRyohi\b", "Ruby"),
    (r"\bTeacher Nekome\b", "Nekome-sensei"),
    (r"\bCat-eye teacher\b", "Nekome-sensei"),
    (r"\bCat Eye Teacher\b", "Nekome-sensei"),
    (r"\bNekome teacher\b", "Nekome-sensei"),
    (r"\bMs\. Nekome\b", "Nekome-sensei"),
    (r"\bMr\. Nekome\b", "Nekome-sensei"),
    (r"\bYoukai Academy\b", "Youkai Academy"),
    (r"\bYokai Academy\b", "Youkai Academy"),
    (r"\bNewspaper Club\b", "Newspaper Club"),
    (r"\bMizore-chan\b", "Mizore-chan"),
    (r"\bKurumu-chan\b", "Kurumu-chan"),
    (r"\bYukari-chan\b", "Yukari-chan"),
    (r"\bKokoa-chan\b", "Kokoa-chan"),
    (r"\bGin-kun\b", "Gin-kun"),
    (r"\bGin senpai\b", "Gin-senpai"),
    (r"\bSenior Gin\b", "Gin-senpai"),
]


def clean_jp(text: str) -> str:
    t = text
    for k, v in JP_NORMALIZATIONS.items():
        t = t.replace(k, v)
    t = re.sub(r"\[RUBY\]", " ", t)
    t = re.sub(r"\[B:[0-9A-Fa-f]{2}\]", "", t)
    t = re.sub(r"\[C:\d+\]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def post_process_en(text: str, orig_ja: str) -> str:
    t = text
    for pat, rep in NAME_REPLACEMENTS:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    # Restore trailing button control tags if present in original
    if orig_ja.endswith("[B:19][B:01]") and not t.endswith("[B:19][B:01]"):
        t += "[B:19][B:01]"
    elif orig_ja.endswith("[B:19]") and not t.endswith("[B:19]"):
        t += "[B:19]"
    # Word wrap to fit PS2 speech box
    return wrap_english_text(t, max_cols=34, max_lines=3)


def translate_batch_gtx(texts: List[str], retries: int = 3) -> List[str]:
    if not texts:
        return []
    cleaned = [clean_jp(t) for t in texts]
    delimiter = "\n@@@\n"
    query = delimiter.join(cleaned)
    for attempt in range(retries):
        try:
            r = requests.post(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "ja", "tl": "en", "dt": "t"},
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            if r.status_code == 200:
                raw_json = r.json()
                translated_full = "".join(chunk[0] for chunk in raw_json[0] if chunk and chunk[0])
                parts = [p.strip() for p in translated_full.split("@@@")]
                if len(parts) == len(texts):
                    return parts
                # If delimiter split count mismatch, fall back to individual translations
                break
            time.sleep(1.0 * (attempt + 1))
        except Exception:
            time.sleep(1.0 * (attempt + 1))

    # Fallback to one-by-one translation
    results = []
    for c in cleaned:
        if not c:
            results.append("")
            continue
        try:
            r = requests.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": "ja", "tl": "en", "dt": "t", "q": c},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            raw_json = r.json()
            trans = "".join(chunk[0] for chunk in raw_json[0] if chunk and chunk[0]).strip()
            results.append(trans)
            time.sleep(0.1)
        except Exception:
            results.append("")
    return results


def run_translation(limit: int = 0, batch_size: int = 30):
    ext_path = Path("extracted_text/strings_dialogue.json")
    trans_path = Path("translations/strings_dialogue.json")

    with open(ext_path, "r", encoding="utf-8") as f:
        ext_data = json.load(f)

    with open(trans_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)

    # Index translations by ID
    trans_map = {s["id"]: s for s in trans_data["strings"]}

    to_translate = []
    for s in ext_data["strings"]:
        en = s.get("translations", {}).get("en", "").strip()
        if not en and s.get("original_ja", "").strip():
            to_translate.append(s)

    total_needed = len(to_translate)
    if limit > 0:
        to_translate = to_translate[:limit]

    print(f"Total untranslated dialogue lines: {total_needed}. Processing: {len(to_translate)}")

    translated_count = 0
    t0 = time.time()

    for i in range(0, len(to_translate), batch_size):
        chunk = to_translate[i : i + batch_size]
        raw_jp = [s["original_ja"] for s in chunk]
        en_results = translate_batch_gtx(raw_jp)

        for s, orig_ja, en_raw in zip(chunk, raw_jp, en_results):
            if en_raw:
                final_en = post_process_en(en_raw, orig_ja)
                s.setdefault("translations", {})["en"] = final_en
                if s["id"] in trans_map:
                    trans_map[s["id"]].setdefault("translations", {})["en"] = final_en
                translated_count += 1

        elapsed = time.time() - t0
        rate = translated_count / elapsed if elapsed > 0 else 0
        print(f"Translated {translated_count}/{len(to_translate)} ({translated_count/len(to_translate)*100:.1f}%) - {rate:.1f} lines/sec")

        # Save checkpoint every 150 lines
        if translated_count % 150 < batch_size or i + batch_size >= len(to_translate):
            with open(ext_path, "w", encoding="utf-8") as f:
                json.dump(ext_data, f, ensure_ascii=False, indent=2)
            with open(trans_path, "w", encoding="utf-8") as f:
                json.dump(trans_data, f, ensure_ascii=False, indent=2)

        time.sleep(0.3)

    print(f"Batch completed! Successfully translated {translated_count} lines.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    run_translation(limit=limit)
