"""
Rosario + Vampire (Capu 2) PS2 Multi-Language Patcher.
Standalone distributable tool for end users.
Can be executed as a script or compiled into an executable (.exe).
"""

import sys
import argparse
from pathlib import Path
from patcher import GamePatcher


BANNER = r"""
======================================================================
     ROSARIO + VAMPIRE CAPU 2: KOI TO YUME NO RHAPSODIA (PS2)
               COMMUNITY TRANSLATION PATCHER
======================================================================
"""

LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "ja": "Japanese (Original)"
}


def find_default_iso() -> Path | None:
    # 1. Check ./iso/
    iso_dir = Path("iso")
    if iso_dir.exists():
        isos = list(iso_dir.glob("*.iso"))
        if isos:
            return isos[0]
    # 2. Check current directory
    local_isos = list(Path(".").glob("*.iso"))
    if local_isos:
        return local_isos[0]
    return None


def print_progress(step: int, total_steps: int, message: str):
    pct = int((step / total_steps) * 100)
    bar_len = 30
    filled = int(bar_len * step / total_steps)
    bar = "=" * filled + "-" * (bar_len - filled)
    print(f"[{bar}] {pct:>3}% - {message}")


def interactive_wizard():
    print(BANNER)
    
    # 1. Locate ISO
    default_iso = find_default_iso()
    if default_iso:
        print(f"Detected ISO: {default_iso.name}")
        choice = input(f"Press Enter to use this ISO or type path to another: ").strip().strip('"')
        iso_path = Path(choice) if choice else default_iso
    else:
        while True:
            choice = input("Enter path to your clean Rosario + Vampire PS2 ISO: ").strip().strip('"')
            iso_path = Path(choice)
            if iso_path.exists():
                break
            print(f"File not found: '{choice}'. Please try again.")

    # 2. Load languages
    patcher = GamePatcher(clean_iso_path=iso_path, translations_dir=None)
    supported_langs = patcher.get_supported_languages()
    if not supported_langs:
        print("Error: No translation files found in 'translations/' or 'extracted_text/' directory.")
        sys.exit(1)

    print("\nSelect the language to translate your ISO to:")
    for idx, lang in enumerate(supported_langs, start=1):
        full_name = LANGUAGE_NAMES.get(lang, lang.upper())
        print(f"  [{idx}] {full_name} ({lang})")

    while True:
        choice = input(f"\nEnter choice (1-{len(supported_langs)}): ").strip()
        try:
            sel_idx = int(choice) - 1
            if 0 <= sel_idx < len(supported_langs):
                selected_lang = supported_langs[sel_idx]
                break
        except ValueError:
            pass
        print(f"Invalid selection '{choice}'. Please choose a number from 1 to {len(supported_langs)}.")

    out_default = f"Rosario_to_Vampire_Capu2_{selected_lang.upper()}.iso"
    out_input = input(f"\nEnter output ISO filename [default: {out_default}]: ").strip().strip('"')
    output_iso = Path(out_input) if out_input else Path(out_default)

    print(f"\nStarting patch process -> Language: [{selected_lang.upper()}]...")
    patcher.patch_iso(selected_lang, output_iso, progress_callback=print_progress)
    print(f"\nSUCCESS! Patched ISO created at: {output_iso.resolve()}")
    print("You can now boot this image in PCSX2 or burn/install it to your PS2.")


def main():
    parser = argparse.ArgumentParser(description="Rosario + Vampire PS2 Translation Patcher")
    parser.add_argument("--iso", type=str, help="Path to clean Japanese PS2 ISO")
    parser.add_argument("--lang", type=str, help="Target language code (e.g. en, es, fr)")
    parser.add_argument("--out", type=str, help="Output path for the patched ISO")
    parser.add_argument(
        "--translations",
        type=str,
        default=None,
        help="Directory containing translation JSON files (defaults to translations/ and extracted_text/)",
    )
    args = parser.parse_args()

    if not args.iso or not args.lang:
        interactive_wizard()
        return

    iso_path = Path(args.iso)
    if not iso_path.exists():
        print(f"Error: ISO not found: {iso_path}")
        sys.exit(1)

    output_iso = Path(args.out) if args.out else Path(f"Rosario_Capu2_{args.lang.upper()}.iso")
    patcher = GamePatcher(clean_iso_path=iso_path, translations_dir=args.translations)
    patcher.patch_iso(args.lang, output_iso, progress_callback=print_progress)
    print(f"Successfully generated: {output_iso}")


if __name__ == "__main__":
    main()
