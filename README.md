# Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia — PS2 Translation Patch

Pure Python translation and ISO patching toolkit for the PlayStation 2 visual novel **"Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia"** (`SLPM_551.89`, Japan).

- **Zero external dependencies:** Uses only the Python 3 standard library.
- **Copyright-safe repository layout:** The repository tracks only pointer metadata and community translations (`translations/`), while raw Japanese game text (`extracted_text/`) is extracted locally from the user's own clean ISO and ignored by Git.

---

## Project Layout

```text
rosario-vamprie-ps2-patch/
├── iso/                            # Place your clean Japanese PS2 ISO here (git-ignored)
├── translations/                   # Redistributable translation files (tracked in Git, NO original Japanese text)
│   ├── strings_dialogue.json       # Event script pointers & translations (725 .evb scripts)
│   ├── strings_executable.json     # SLPM_551.89 UI/menu/save pointers & translations
│   └── strings_system.json         # System container pointers & translations (sys000.bin, sys001.bin)
├── extracted_text/                 # Local reference dump WITH original Japanese strings (git-ignored)
│   ├── strings_dialogue.json
│   ├── strings_executable.json
│   └── strings_system.json
└── scripts/
    ├── distributable_patcher.py    # End-user ISO patcher (interactive wizard & CLI)
    ├── extract_text.py             # Extracts Japanese strings locally & syncs translations
    ├── patcher.py                  # Core patching engine (ELF, AFS, 64-byte PAC, LZR, EVB bytecode)
    ├── translation_manager.py      # JSON schema loader, saver, and progress tracker
    ├── font_mapper.py              # Custom 16-bit glyph & half-width ASCII encoder/decoder
    ├── lzr_tool.py                 # HuneX LZR compressor/decompressor & EVB bytecode rebuilder
    ├── pac_tool.py                 # HuneX PAC archive reader & 64-byte aligned builder
    ├── afs_tool.py                 # CRI Middleware AFS container parser
    ├── iso_tool.py                 # ISO 9660 reader & in-place binary patcher
    └── build_exe.py                # Optional PyInstaller builder for standalone .exe distribution
```

---

## 1. How to Apply the Patch (Players)

### Requirements
- Python 3.10+ installed.
- A clean copy of the Japanese PS2 ISO: `Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso` (`SLPM_551.89`).

### Interactive Mode
Place your clean ISO inside the `iso/` folder (or anywhere on disk) and run:
```bash
python scripts/distributable_patcher.py
```
Follow the on-screen prompts to select your ISO and target language (`en`, `es`, `fr`, etc.).

### Command-Line Mode
```bash
python scripts/distributable_patcher.py --iso "iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso" --lang en --out "Rosario_Capu2_EN.iso"
```
Boot the generated `Rosario_Capu2_EN.iso` in **PCSX2** or on real PS2 hardware.

---

## 2. How to Extract Japanese Text & Translate (Contributors)

To keep this repository free of copyrighted Japanese script dumps, `translations/*.json` omits the `"original_ja"` field. Translators can generate the full Japanese reference files locally from their own ISO.

### Step 1: Extract Japanese Text Locally
Place your clean Japanese ISO in `iso/` and run:
```bash
python scripts/extract_text.py --iso "iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso"
```
This command:
1. Preserves any existing translations from `translations/` and `extracted_text/`.
2. Generates **`extracted_text/*.json`** (git-ignored) containing `"original_ja"` alongside `"translations"` for every dialogue line, choice, and UI string.
3. Generates **`translations/*.json`** (redistributable) containing only IDs, file/offset pointers, speaker/voice context, and `"translations"` (without `"original_ja"`).

### Step 2: Edit Translations
Open the files in `extracted_text/` (`strings_dialogue.json`, `strings_executable.json`, `strings_system.json`) where you can see `"original_ja"` for reference:
```json
{
  "id": "dialogue_00002",
  "source_file": "afstmp/1.afs:afstmp/dat/pac000999.pac:e100010.evb",
  "offset_hex": "0x0080",
  "original_ja": "萌香を人質に\nとるなんて…\n卑怯だぞ[RUBY]貴様！",
  "translations": {
    "en": "Taking Moka hostage...\nHow cowardly,[RUBY]you bastard!",
    "es": "Tomar a Moka como rehen...\n¡Que cobarde,[RUBY]maldito!",
    "fr": "Prendre Moka en otage...\nQuel lache,[RUBY]enfoire !"
  },
  "context": "Dialogue (e100010.evb spk=0, voice=-1)"
}
```
- Keep `[RUBY]` tags if you want inline furigana/emphasis formatting, or omit them for plain text.
- Dialogue strings in `.evb` scripts automatically wrap lines and relocate bytecode jump targets (`0x02`, `0x03`, `0x16`, `0x1E`), so English dialogue lines are not restricted to the original Japanese byte length.
- Executable UI strings (`SLPM_551.89`) and `sys000.bin` / `sys001.bin` strings are patched in-place and respect the `max_bytes` hint shown in `"context"`.

### Step 3: Sync Translations for GitHub Distribution
After editing `extracted_text/*.json`, sync your changes into the redistributable `translations/*.json` folder:
```bash
python scripts/extract_text.py --sync-only
```
This updates `translations/*.json` with all your new translations while stripping `"original_ja"`, leaving `translations/` ready to commit and push to GitHub.

---

## 3. Building a Standalone Windows Executable (Optional)

To package the patcher into a single `Rosario_Vampire_Patcher.exe` for users without Python:
```bash
python scripts/build_exe.py
```
Distribute `dist/Rosario_Vampire_Patcher.exe` alongside the `translations/` folder.