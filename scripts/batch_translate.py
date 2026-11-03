"""
100% PURE LOCAL MarianMT Batch Translator for Rosario + Vampire Capu 2 (PS2).
Uses Helsinki-NLP/opus-mt-ja-en with PyTorch CPU inference and domain post-processing.
Zero external web API calls, zero rate-limits, zero network dependency.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict

import torch
import transformers

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
    "ツヮ": "ツレ",
    "カサ": "のか",
    "見也物": "見世物",
    "咋日": "昨日",
}

NAME_REPLACEMENTS = [
    (r"\bTsukine\b", "Tsukune"),
    (r"\bMooncutter\b", "Tsukune"),
    (r"\bMoeka\b", "Moka"),
    (r"\bMurasaki-chan\b", "Yukari-chan"),
    (r"\bMurasaki\b", "Yukari"),
    (r"\bpurple\b", "Yukari"),
    (r"\bPurple\b", "Yukari"),
    (r"\bMidorihime\b", "Ruby"),
    (r"\bRyohi\b", "Ruby"),
    (r"\bMiss Greene\b", "Ruby-san"),
    (r"\bMs\. Greene\b", "Ruby-san"),
    (r"\bGreene\b", "Ruby"),
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
    (r"\bYou're a dreamer, aren't you\?\b", "Kurumu-chan!?"),
    (r"\bYou're a dreamer!\b", "Kurumu-chan!?"),
    (r"\bDreams, are you all right\?\b", "Kurumu, are you all right?"),
    (r"\bNo, no, wait!\b", "Kurumu-chan, wait!"),
]

EXACT_PHRASE_FALLBACKS = {
    "えっ": "Eh?",
    "あ…": "Ah...",
    "う～ん…": "Hmm...",
    "うーん…": "Hmm...",
    "うん": "Yeah.",
    "はい": "Yes.",
    "どうしたの？": "What's wrong?",
    "おはよう": "Good morning.",
    "ありがとう": "Thank you.",
    "さようなら": "Goodbye.",
    "…": "...",
    "……": "......",
    "！？": "!?",
    "？！": "?!",
}


class MarianBatchTranslator:
    def __init__(self, model_name: str = "Helsinki-NLP/opus-mt-ja-en"):
        print(f"Loading local MarianMT model ({model_name})...", flush=True)
        torch.set_num_threads(min(8, os.cpu_count() or 4))
        self.tokenizer = transformers.MarianTokenizer.from_pretrained(model_name)
        self.model = transformers.MarianMTModel.from_pretrained(model_name)
        self.model.eval()
        print("Model loaded successfully.", flush=True)

    def translate_batch(self, texts: List[str]) -> List[str]:
        if not texts:
            return []
        cleaned = [clean_jp(t) for t in texts]
        
        # Check exact fallback phrases
        results = [None] * len(cleaned)
        indices_to_model = []
        texts_to_model = []

        for idx, t in enumerate(cleaned):
            if not t:
                results[idx] = ""
            elif t in EXACT_PHRASE_FALLBACKS:
                results[idx] = EXACT_PHRASE_FALLBACKS[t]
            else:
                indices_to_model.append(idx)
                texts_to_model.append(t)

        if texts_to_model:
            inputs = self.tokenizer(texts_to_model, return_tensors="pt", padding=True, truncation=True, max_length=128)
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=64,
                    num_beams=2,
                    no_repeat_ngram_size=2
                )
            for orig_idx, out in zip(indices_to_model, outputs):
                decoded = self.tokenizer.decode(out, skip_special_tokens=True).strip()
                results[orig_idx] = decoded

        return [r if r is not None else "" for r in results]


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


def run_translation(limit: int = 0, batch_size: int = 64):
    ext_path = Path("extracted_text/strings_dialogue.json")
    trans_path = Path("translations/strings_dialogue.json")

    with open(ext_path, "r", encoding="utf-8") as f:
        ext_data = json.load(f)

    with open(trans_path, "r", encoding="utf-8") as f:
        trans_data = json.load(f)

    trans_map = {s["id"]: s for s in trans_data["strings"]}

    # Identify dialogue needing translation
    to_translate = []
    control_re = re.compile(r"\[(?:B:[0-9A-Fa-f]{2}|C:\d+|RUBY)\]|\s+")

    kanji_hiragana = re.compile(r"[\u3040-\u309f\u4e00-\u9fff]")

    for s in ext_data["strings"]:
        en = s.get("translations", {}).get("en", "").strip()
        raw = s.get("original_ja", "")
        # If en is empty OR en still has raw Japanese text in it, re-translate!
        if not en or kanji_hiragana.search(en):
            if not control_re.sub("", raw):
                # Pure control bytes line (e.g. [B:19][B:01]) - keep as is!
                s.setdefault("translations", {})["en"] = raw
                s["translations"]["es"] = raw
                s["translations"]["fr"] = raw
                if s["id"] in trans_map:
                    t_item = trans_map[s["id"]].setdefault("translations", {})
                    t_item["en"] = raw
                    t_item["es"] = raw
                    t_item["fr"] = raw
            else:
                to_translate.append(s)

    total_needed = len(to_translate)
    if limit > 0:
        to_translate = to_translate[:limit]

    print(f"100% Local Neural Engine: {total_needed} lines need translation. Processing {len(to_translate)} in this run...")

    engine = MarianBatchTranslator()
    translated_count = 0
    t0 = time.time()

    for i in range(0, len(to_translate), batch_size):
        chunk = to_translate[i : i + batch_size]
        raw_jp = [s["original_ja"] for s in chunk]
        en_results = engine.translate_batch(raw_jp)

        for s, orig_ja, en_raw in zip(chunk, raw_jp, en_results):
            if en_raw and not kanji_hiragana.search(en_raw):
                final_en = post_process_en(en_raw, orig_ja)
            else:
                final_en = post_process_en(en_raw or "...", orig_ja)
            
            s.setdefault("translations", {})["en"] = final_en
            s["translations"]["es"] = final_en
            s["translations"]["fr"] = final_en

            if s["id"] in trans_map:
                t_item = trans_map[s["id"]].setdefault("translations", {})
                t_item["en"] = final_en
                t_item["es"] = final_en
                t_item["fr"] = final_en
            translated_count += 1

        elapsed = time.time() - t0
        rate = translated_count / elapsed if elapsed > 0 else 0
        pct = translated_count / len(to_translate) * 100
        print(f"Progress: {translated_count}/{len(to_translate)} ({pct:.1f}%) - Speed: {rate:.1f} lines/sec", flush=True)

        # Checkpoint save atomically every 300 lines or at the end
        if translated_count % 300 < batch_size or i + batch_size >= len(to_translate):
            tmp_ext = ext_path.with_suffix(".tmp")
            tmp_trans = trans_path.with_suffix(".tmp")
            with open(tmp_ext, "w", encoding="utf-8") as f:
                json.dump(ext_data, f, ensure_ascii=False, indent=2)
            with open(tmp_trans, "w", encoding="utf-8") as f:
                json.dump(trans_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_ext, ext_path)
            os.replace(tmp_trans, trans_path)

    total_time = time.time() - t0
    print(f"Done! Translated {translated_count} lines in {total_time:.1f}s ({translated_count/total_time:.1f} lines/sec).")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    run_translation(limit=limit)
