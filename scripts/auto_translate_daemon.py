"""
Continuous background translation runner for Rosario + Vampire PS2.
Runs batch translation in continuous cycles until 100% of all dialogue lines
across all days are translated, then automatically rebuilds Rosario_Capu2_EN.iso.
Logs progress to translations/translate_progress.log.
"""

import os
import sys
import time
from pathlib import Path

# Ensure utf-8 output
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
os.chdir(ROOT_DIR)
sys.path.insert(0, str(ROOT_DIR / "scripts"))

LOG_FILE = ROOT_DIR / "translations" / "translate_progress.log"


def log(msg: str):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    log("=== Starting Full-Game Background Translator ===")
    import json
    import subprocess

    ext_path = Path("extracted_text/strings_dialogue.json")

    while True:
        with open(ext_path, "r", encoding="utf-8") as f:
            ext_data = json.load(f)

        untrans = sum(
            1
            for s in ext_data["strings"]
            if not s.get("translations", {}).get("en", "").strip()
            and s.get("original_ja", "").strip()
        )
        total = len(ext_data["strings"])
        done = total - untrans

        log(f"Status: {done}/{total} translated ({done/total*100:.1f}%), {untrans} remaining.")

        if untrans == 0:
            log("SUCCESS: 100% of all dialogue lines are translated!")
            log("Rebuilding Rosario_Capu2_EN.iso with full translation...")
            cmd = [
                sys.executable,
                "scripts/patcher.py",
                "--input-iso",
                "iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso",
                "--output-iso",
                "Rosario_Capu2_EN.iso",
                "--lang",
                "en",
            ]
            subprocess.run(cmd, check=True)
            log("ISO patch complete! All done!")
            break

        # Run a batch of up to 3000 lines
        batch_to_run = min(3000, untrans)
        log(f"Translating next batch of {batch_to_run} lines with 100% local neural engine...")

        from batch_translate import run_translation

        try:
            run_translation(limit=batch_to_run, batch_size=100)
        except Exception as e:
            log(f"Warning: batch translation encountered error: {e}. Retrying in 5s...")
            time.sleep(5)

        # Brief pause between chunks to be gentle on CPU / network
        time.sleep(2)


if __name__ == "__main__":
    main()
