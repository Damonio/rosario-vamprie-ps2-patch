"""
Patching engine for Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia (PS2, SLPM_551.89).
Reads multi-language JSON translation files (from translations/ or extracted_text/) and injects translations into:
  1. SLPM_551.89 (Custom 16-bit glyph UI/save/location strings & Shift-JIS system strings)
  2. RVCAPU2.AFS -> 1.afs -> sys000.bin & sys001.bin
  3. RVCAPU2.AFS -> 1.afs -> pac000999.pac (Rebuilds .evb event bytecode with full pointer relocation,
     hardware-exact LZR header & optimal compression, 64-byte PAC alignment, and exact 0xE0800 size preservation)
Pure Python - zero external dependencies.
"""

import os
import re
import shutil
import struct
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from iso_tool import IsoHandler
from afs_tool import AfsArchive
from pac_tool import PacArchive
from lzr_tool import decompress_lzr, compress_lzr, rebuild_evb
from font_mapper import encode_game_string
from translation_manager import TranslationProject
import tex_tool


def _parse_max_bytes(context: str, default_len: int) -> int:
    m = re.search(r"max_bytes=(\d+)", context or "")
    if m:
        return int(m.group(1))
    return default_len


def _measure_null_terminated_span(buf: bytes | bytearray, offset: int, even_aligned: bool = False) -> int:
    end = offset
    if even_aligned:
        while end + 1 < len(buf) and (buf[end] != 0 or buf[end + 1] != 0):
            end += 2
    else:
        while end < len(buf) and buf[end] != 0:
            end += 1
    return max(0, end - offset)


class GamePatcher:
    def __init__(self, clean_iso_path: Path | str, translations_dir: Optional[Path | str] = None):
        self.clean_iso_path = Path(clean_iso_path)
        if not self.clean_iso_path.exists():
            raise FileNotFoundError(f"Clean ISO not found at: {self.clean_iso_path}")

        if translations_dir is not None:
            self.translations_dir = Path(translations_dir)
        else:
            # Prefer local extracted_text/ if populated, otherwise fall back to redistributable translations/
            ext_dir = Path("extracted_text")
            dist_dir = Path("translations")
            if ext_dir.exists() and list(ext_dir.glob("*.json")):
                self.translations_dir = ext_dir
            else:
                self.translations_dir = dist_dir

    def _get_json_dirs(self) -> List[Path]:
        """
        Returns translation directories to load from (merges translations/ and extracted_text/ if both exist).
        """
        dirs = []
        for candidate in [Path("translations"), Path("extracted_text"), self.translations_dir]:
            if candidate.exists() and candidate not in dirs:
                dirs.append(candidate)
        return dirs

    def _load_merged_projects(self) -> List[TranslationProject]:
        """
        Loads translation JSONs, giving priority to self.translations_dir when the same string ID/offset is translated.
        """
        projects_by_name: Dict[str, TranslationProject] = {}
        # Load fallback dirs first, then self.translations_dir last so its non-empty translations win
        ordered_dirs = [d for d in self._get_json_dirs() if d != self.translations_dir]
        if self.translations_dir.exists():
            ordered_dirs.append(self.translations_dir)

        for d in ordered_dirs:
            for json_file in sorted(d.glob("*.json")):
                try:
                    proj = TranslationProject.load(json_file)
                except Exception:
                    continue
                if json_file.name not in projects_by_name:
                    projects_by_name[json_file.name] = proj
                else:
                    existing = projects_by_name[json_file.name]
                    by_key = {(s.source_file, s.offset_hex): s for s in existing.strings}
                    for s in proj.strings:
                        key = (s.source_file, s.offset_hex)
                        if key in by_key:
                            for lang, val in s.translations.items():
                                if val and val.strip():
                                    by_key[key].translations[lang] = val
                        else:
                            existing.strings.append(s)
        return list(projects_by_name.values())

    def get_supported_languages(self) -> List[str]:
        """
        Scans all JSON files to find all defined language codes.
        """
        languages = set()
        for proj in self._load_merged_projects():
            languages.update(proj.get_available_languages())
        return sorted(list(languages))

    def patch_iso(self, target_lang: str, output_iso_path: Path | str, progress_callback=None) -> Path:
        output_iso_path = Path(output_iso_path)
        output_iso_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(1, 5, f"Creating copy of ISO for [{target_lang.upper()}]...")

        if self.clean_iso_path.resolve() != output_iso_path.resolve():
            shutil.copyfile(self.clean_iso_path, output_iso_path)

        iso = IsoHandler(output_iso_path)
        projects = self._load_merged_projects()

        if progress_callback:
            progress_callback(2, 5, "Applying executable translations (SLPM_551.89)...")

        # 1. Patch SLPM_551.89 in place (works both with and without original_ja in JSON)
        if "SLPM_551.89" in iso.entries:
            slpm_entry = iso.entries["SLPM_551.89"]
            with open(output_iso_path, "r+b") as f:
                f.seek(slpm_entry.offset)
                slpm_bytes = bytearray(f.read(slpm_entry.size))

                # Character speaker name table definition
                # Actual speaker pointer table in SLPM_551.89 is at file offset 0x1047B8 (VA 0x002037B8)
                # with 30 entries (32-bit pointers).
                #
                # Safe zero-padding allocation in .data section:
                # File offset 0x1306F0 (VA 0x0022F6F0) has 1,060 bytes of zero padding with no code pointers.
                # Allocating 27 unique speaker entries at 32 bytes each uses 864 bytes (< 1060).
                # We redirect the pointers in the table at 0x1047B8 to point into this safe .data padding.
                # .rodata and .sdata are left 100% untouched to prevent crashes or jump table corruption!
                SPEAKER_TABLE_POS = 0x1047B8
                SPEAKER_ALLOC_BASE_OFF = 0x1306F0
                SPEAKER_ALLOC_BASE_VA = 0x0022F6F0
                SPEAKER_SLOT_SIZE = 32

                SPEAKER_ID_MAP = {
                    "sys_char_01": [0],         # Tsukune
                    "sys_char_02": [1, 2],      # Moka
                    "sys_char_03": [3],         # Kurumu
                    "sys_char_04": [4],         # Yukari
                    "sys_char_05": [5],         # Mizore
                    "sys_char_06": [6],         # Midou
                    "sys_char_07": [7],         # Kokoa
                    "sys_char_08": [8],         # Shizuka
                    "sys_char_09": [9],         # Rin
                    "sys_char_10": [10],        # Hitomi
                    "sys_char_11": [11],        # Ginei
                    "sys_char_12": [12],        # Nekonome
                    "sys_spk_01":  [13],        # Ko-chan
                    "sys_spk_02":  [14],        # Driver
                    "sys_char_13": [15],        # Bastard
                    "sys_char_14": [16],        # Koutarou
                    "sys_char_15": [17],        # Kasahara
                    "sys_char_16": [18],        # Bouzaburou
                    "sys_char_17": [19],        # Sakasaku
                    "sys_char_18": [20],        # Voice
                    "sys_char_19": [21],        # Karis
                    "sys_spk_03":  [22, 28],    # Boy
                    "sys_spk_04":  [23, 29],    # Girl
                    "sys_spk_05":  [24],        # Radio
                    "sys_char_20": [25],        # Foreigner
                    "sys_char_21": [26],        # ???
                    "sys_spk_06":  [27],        # Mascot
                }

                # Collect translations from strings_system.json
                slpm_trans: Dict[str, str] = {}
                for proj in projects:
                    for s in proj.strings:
                        if s.source_file == "SLPM_551.89":
                            t = s.translations.get(target_lang, "").strip()
                            if t:
                                slpm_trans[s.id] = t

                for slot_idx, (spk_id, table_indices) in enumerate(SPEAKER_ID_MAP.items()):
                    trans = slpm_trans.get(spk_id)
                    if trans:
                        alloc_off = SPEAKER_ALLOC_BASE_OFF + slot_idx * SPEAKER_SLOT_SIZE
                        va = SPEAKER_ALLOC_BASE_VA + slot_idx * SPEAKER_SLOT_SIZE
                        enc = encode_game_string(trans, use_halfwidth_ascii=True, auto_wrap=False) + b"\x00\x00"
                        if len(enc) > SPEAKER_SLOT_SIZE:
                            enc = enc[:SPEAKER_SLOT_SIZE - 2] + b"\x00\x00"
                        slpm_bytes[alloc_off : alloc_off + len(enc)] = enc
                        for tidx in table_indices:
                            struct.pack_into("<I", slpm_bytes, SPEAKER_TABLE_POS + tidx * 4, va)

                # Patch system prompts and save/load message pointer table at 0x105500
                # Safe zero-padding allocation at file offset 0x130C20 (VA 0x0022FC20) has 6,912 continuous zero bytes.
                SYSTEM_PROMPT_TABLE_POS = 0x105500
                SYSTEM_PROMPT_BASE_OFF = 0x130C20
                SYSTEM_PROMPT_BASE_VA = 0x0022FC20

                SYSTEM_PROMPTS = {
                    "en": {
                        0: "Saving data.\nDo not remove Memory Card (PS2) or turn off the console.",
                        1: "No Memory Card (PS2) inserted in Slot 1.\n[B:19][B:03] Return",
                        2: "There is no loadable data on the\nMemory Card (PS2) in Slot 1.\n[B:19][B:03] Return",
                        3: "Load this data?",
                        4: "Loading data...",
                        5: "Data loaded successfully.",
                        6: "The data is corrupted.\n[B:19][B:03] Return",
                        7: "Failed to load data!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        8: "Insufficient free space on Memory Card (PS2) in Slot 1.\nTo create save data, [B:1B] is required.",
                        9: "No save data on Memory Card (PS2) in Slot 1.\nTo create data, [B:1B] is required.",
                        10: "Data on Memory Card (PS2) in Slot 1 is corrupted.\nOverwrite anyway?",
                        11: "Overwrite existing data?",
                        12: "Save to this slot?",
                        13: "Data saved successfully.",
                        14: "Creating save data.\nDo not remove Memory Card (PS2) or turn off the console.",
                        15: "Save data creation complete.",
                        16: "Formatting corrupted data...\nDo not remove Memory Card (PS2) or turn off the console.",
                        17: "Format failed!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        18: "Failed to create save data!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        19: "Failed to save system data!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        20: "Failed to save data!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        21: "Failed to format corrupted data!\nCheck Memory Card (PS2) in Slot 1 and try again.\n[B:19][B:02] Continue",
                        22: "Progress is not saved. Proceed anyway?",
                        23: "No Memory Card (PS2) inserted in Slot 1.\nTo create save data, [B:1B] is required.",
                        24: "No save data on Memory Card (PS2) in Slot 1.\nTo create data, [B:1B] is required.",
                        25: "Insufficient free space on Memory Card (PS2) in Slot 1.\nTo create save data, [B:1B] is required.",
                        26: "Failed to load system data!\nCheck Memory Card (PS2) in Slot 1 and try again.\nStart game anyway?",
                        27: "System data is corrupted.\nCreate new system data?",
                        28: "Save changed settings?",
                        29: "Save system data?",
                        30: "Save game clear data?",
                        31: "Return to Title Screen?",
                        33: "No Data",
                        34: "June 15", 35: "June 16", 36: "June 17", 37: "June 18", 38: "June 19",
                        39: "June 20", 40: "June 21", 41: "June 22", 42: "June 23", 43: "June 24",
                        44: "Youkai Academy", 45: "School Gate", 46: "Classroom", 47: "Hallway",
                        48: "Rooftop", 49: "Infirmary", 50: "School Store", 51: "Hallway",
                        52: "Newspaper Club", 53: "Fan Club Union", 54: "Tsukune Room",
                        55: "Courtyard", 56: "Cafeteria", 57: "Cooking Lab", 58: "Pond",
                        59: "Cemetery", 60: "Live Stage", 63: "Ending",
                    },
                    "es": {
                        0: "Guardando datos.\nNo extraiga la Memory Card (PS2) ni apague la consola.",
                        1: "No hay Memory Card (PS2) en la Ranura 1.\n[B:19][B:03] Volver",
                        2: "No hay datos para cargar en la\nMemory Card (PS2) en la Ranura 1.\n[B:19][B:03] Volver",
                        3: "¿Cargar estos datos?",
                        4: "Cargando datos...",
                        5: "Datos cargados con éxito.",
                        6: "Los datos están dañados.\n[B:19][B:03] Volver",
                        7: "¡Fallo al cargar datos!\nCompruebe la Memory Card (PS2) en la Ranura 1.\n[B:19][B:02] Continuar",
                        11: "¿Sobrescribir datos?",
                        12: "¿Guardar en esta ranura?",
                        13: "Datos guardados con éxito.",
                        22: "Progreso no guardado. ¿Continuar?",
                        27: "Datos del sistema dañados.\n¿Crear nuevos datos?",
                        28: "¿Guardar ajustes?",
                        29: "¿Guardar datos de sistema?",
                        30: "¿Guardar datos completados?",
                        31: "¿Volver a la pantalla de título?",
                        33: "Sin datos",
                    }
                }

                prompts_dict = dict(SYSTEM_PROMPTS.get("en", {}))
                if target_lang in SYSTEM_PROMPTS:
                    prompts_dict.update(SYSTEM_PROMPTS[target_lang])

                curr_prompt_off = SYSTEM_PROMPT_BASE_OFF
                curr_prompt_va = SYSTEM_PROMPT_BASE_VA
                for p_idx, p_text in prompts_dict.items():
                    p_enc = encode_game_string(p_text, use_halfwidth_ascii=True, auto_wrap=False) + b"\x00\x00"
                    if len(p_enc) % 4 != 0:
                        p_enc += b"\x00" * (4 - (len(p_enc) % 4))
                    if curr_prompt_off + len(p_enc) <= 0x132760:
                        slpm_bytes[curr_prompt_off : curr_prompt_off + len(p_enc)] = p_enc
                        struct.pack_into("<I", slpm_bytes, SYSTEM_PROMPT_TABLE_POS + p_idx * 4, curr_prompt_va)
                        curr_prompt_off += len(p_enc)
                        curr_prompt_va += len(p_enc)

                f.seek(slpm_entry.offset)
                f.write(slpm_bytes)

        if progress_callback:
            progress_callback(3, 5, "Patching system and dialogue containers in RVCAPU2.AFS...")

        # Collect .evb dialogue translations grouped by script name -> {offset_hex: translated_text}
        evb_translations: Dict[str, Dict[str, str]] = defaultdict(dict)
        for proj in projects:
            for s in proj.strings:
                if "pac000999.pac:" in s.source_file:
                    trans = s.translations.get(target_lang, "").strip()
                    if trans:
                        evb_name = s.source_file.split(":")[-1]
                        evb_translations[evb_name][s.offset_hex] = trans

        # 2. Patch AFS containers (sys000.bin, sys001.bin, and pac000999.pac inside 1.afs)
        if "RVCAPU2.AFS" in iso.entries:
            rv_entry = iso.entries["RVCAPU2.AFS"]
            with open(output_iso_path, "r+b") as f:
                rv_afs = AfsArchive(f, base_offset=rv_entry.offset)
                afs1_info = [e for e in rv_afs.entries if "1.afs" in e.name.lower()]
                if afs1_info:
                    afs1_entry = afs1_info[0]
                    afs1_offset = rv_entry.offset + afs1_entry.offset
                    afs1 = AfsArchive(f, base_offset=afs1_offset)

                    # Patch sys000.bin and sys001.bin in place
                    for sys_name in ("sys000.bin", "sys001.bin"):
                        sys_info = [e for e in afs1.entries if sys_name in e.name.lower()]
                        if sys_info:
                            s_entry = sys_info[0]
                            f.seek(afs1_offset + s_entry.offset)
                            sys_bytes = bytearray(f.read(s_entry.size))
                            modified_sys = False

                            for proj in projects:
                                for s in proj.strings:
                                    if sys_name in s.source_file.lower():
                                        trans = s.translations.get(target_lang, "").strip()
                                        if trans:
                                            offset = int(s.offset_hex, 16)
                                            fallback_len = _measure_null_terminated_span(sys_bytes, offset, even_aligned=False)
                                            max_len = _parse_max_bytes(s.context, fallback_len)
                                            trans_bytes = trans.encode("shift_jis", errors="replace")[:max_len]
                                            if 0 <= offset and max_len > 0 and offset + max_len <= len(sys_bytes):
                                                sys_bytes[offset : offset + max_len] = trans_bytes.ljust(max_len, b"\x00")
                                                modified_sys = True

                            if modified_sys:
                                f.seek(afs1_offset + s_entry.offset)
                                f.write(sys_bytes)

                    # Patch pac000999.pac (.evb dialogue/event scripts)
                    if evb_translations:
                        pac_info = [e for e in afs1.entries if "pac000999.pac" in e.name.lower()]
                        if pac_info:
                            pac_afs_entry = pac_info[0]
                            orig_pac_size = pac_afs_entry.size

                            f.seek(afs1_offset + pac_afs_entry.offset)
                            pac_raw_bytes = f.read(orig_pac_size)
                            pac = PacArchive(pac_raw_bytes)

                            rebuilt_entries = []
                            for entry in pac.entries:
                                script_trans = evb_translations.get(entry.name)
                                if script_trans:
                                    evb_raw = decompress_lzr(entry.data) if entry.is_compressed else entry.data
                                    new_evb_raw = rebuild_evb(
                                        evb_raw, script_trans, use_halfwidth_ascii=True, max_dialogue_bytes=108
                                    )
                                    # Always LZR-compress translated EVB scripts to save space
                                    comp_data = compress_lzr(new_evb_raw)
                                    rebuilt_entries.append({
                                        "name": entry.name,
                                        "data": comp_data,
                                        "is_compressed": True,
                                        "uncomp_size": len(new_evb_raw),
                                        "flag": entry.flag | 0x00010000,
                                        "modified": True,
                                    })
                                else:
                                    rebuilt_entries.append({
                                        "name": entry.name,
                                        "data": entry.data,
                                        "is_compressed": entry.is_compressed,
                                        "uncomp_size": entry.uncomp_size,
                                        "flag": entry.flag,
                                        "modified": False,
                                    })

                            new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=64)

                            # If PAC exceeds orig_pac_size (919,552 bytes), recompress untouched entries
                            if len(new_pac_bytes) > orig_pac_size:
                                for item in rebuilt_entries:
                                    if not item["modified"] and item["is_compressed"]:
                                        raw_untouched = decompress_lzr(item["data"])
                                        recomp = compress_lzr(raw_untouched)
                                        if len(recomp) < len(item["data"]):
                                            item["data"] = recomp
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=64)

                            # If still exceeding, step down alignment to 32, 16, 8, then 4 (word aligned for MIPS)
                            if len(new_pac_bytes) > orig_pac_size:
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=32)
                            if len(new_pac_bytes) > orig_pac_size:
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=16)
                            if len(new_pac_bytes) > orig_pac_size:
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=8)
                            if len(new_pac_bytes) > orig_pac_size:
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=4)

                            if len(new_pac_bytes) > orig_pac_size:
                                raise ValueError(
                                    f"Rebuilt pac000999.pac ({len(new_pac_bytes)} bytes) exceeds "
                                    f"original 1.afs size ({orig_pac_size} bytes)."
                                )

                            # Write rebuilt pac000999.pac padded to exact original size (0xE0800 = 919,552 bytes)
                            # so 1.afs header, 1.afs directory table, and 0.bin sector table remain 100% untouched!
                            f.seek(afs1_offset + pac_afs_entry.offset)
                            f.write(new_pac_bytes.ljust(orig_pac_size, b"\x00"))

                    # Patch translated 2D textures (title buttons, HUD, prompts)
                    self._patch_textures(f, afs1_offset, afs1)

        if progress_callback:
            progress_callback(4, 5, "Verifying sector integrity...")

        if progress_callback:
            progress_callback(5, 5, "Patch complete!")

        return output_iso_path

    def _patch_textures(self, f, afs1_offset: int, afs1: AfsArchive) -> None:
        """
        Patches translated 2D textures (.png -> .tex) into 1.afs and its PAC containers.
        """
        tex_dirs = []
        for candidate in [self.translations_dir / "textures", Path("translations/textures")]:
            if candidate.exists() and candidate not in tex_dirs:
                tex_dirs.append(candidate)

        tex_replacements: Dict[str, bytes] = {}
        for td in tex_dirs:
            for png_file in sorted(td.glob("*.png")):
                base_stem = png_file.stem.lower()
                tex_name = base_stem + ".tex"
                if tex_name not in tex_replacements:
                    try:
                        with open(png_file, "rb") as pf:
                            tex_replacements[tex_name] = tex_tool.png_to_tex(pf.read())
                    except Exception as ex:
                        print(f"Warning: Failed to convert texture {png_file.name}: {ex}")

        if not tex_replacements:
            return

        # 1. Patch standalone textures in 1.afs
        for e in afs1.entries:
            fname = os.path.basename(e.name).lower()
            if fname in tex_replacements:
                new_tex = tex_replacements[fname]
                if len(new_tex) <= e.size:
                    f.seek(afs1_offset + e.offset)
                    f.write(new_tex.ljust(e.size, b"\x00"))

        # 2. Patch textures inside PAC archives in 1.afs (e.g. pac900000.pac, pac000000.pac)
        for e in afs1.entries:
            if e.name.lower().endswith(".pac"):
                f.seek(afs1_offset + e.offset)
                pac_raw = f.read(e.size)
                try:
                    pac = PacArchive(pac_raw)
                except Exception:
                    continue

                pac_needs_rebuild = any(pe.name.lower() in tex_replacements for pe in pac.entries)
                if not pac_needs_rebuild:
                    continue

                rebuilt_entries = []
                for pe in pac.entries:
                    pe_name = pe.name.lower()
                    if pe_name in tex_replacements:
                        new_raw = tex_replacements[pe_name]
                        comp_data = compress_lzr(new_raw) if pe.is_compressed else new_raw
                        rebuilt_entries.append({
                            "name": pe.name,
                            "data": comp_data,
                            "is_compressed": pe.is_compressed,
                            "uncomp_size": len(new_raw),
                            "flag": pe.flag | 0x00010000 if pe.is_compressed else pe.flag,
                            "modified": True,
                        })
                    else:
                        rebuilt_entries.append({
                            "name": pe.name,
                            "data": pe.data,
                            "is_compressed": pe.is_compressed,
                            "uncomp_size": pe.uncomp_size,
                            "flag": pe.flag,
                            "modified": False,
                        })

                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=64)
                if len(new_pac_bytes) <= e.size:
                    f.seek(afs1_offset + e.offset)
                    f.write(new_pac_bytes.ljust(e.size, b"\x00"))


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Patch Rosario + Vampire PS2 ISO with community translations.")
    parser.add_argument("--input-iso", "-i", default="iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso", help="Path to clean Japanese ISO")
    parser.add_argument("--output-iso", "-o", default=None, help="Path for patched output ISO")
    parser.add_argument("--lang", "-l", default="en", choices=["en", "es", "fr"], help="Language code (en, es, fr)")
    parser.add_argument("--translations-dir", "-t", default="translations", help="Directory with translation JSONs")
    args = parser.parse_args()

    iso_in = Path(args.input_iso)
    if not iso_in.exists():
        print(f"Error: Clean ISO not found at '{iso_in}'.")
        sys.exit(1)

    iso_out = Path(args.output_iso) if args.output_iso else Path(f"Rosario_Capu2_{args.lang.upper()}.iso")
    patcher = GamePatcher(clean_iso_path=iso_in, translations_dir=args.translations_dir)

    def _progress(step: int, total: int, msg: str):
        pct = int(step / total * 100)
        bar = "=" * (pct // 2) + "-" * (50 - (pct // 2))
        print(f"[{bar}] {pct:3d}% - {msg}")

    patcher.patch_iso(target_lang=args.lang, output_iso_path=iso_out, progress_callback=_progress)
    print(f"Done! Output generated: {iso_out}")

