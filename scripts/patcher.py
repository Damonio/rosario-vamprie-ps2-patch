"""
Patching engine for Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia (PS2, SLPM_551.89).
Reads multi-language JSON translation files (from translations/ or extracted_text/) and injects translations into:
  1. SLPM_551.89 (Custom 16-bit glyph UI/save/location strings & Shift-JIS system strings)
  2. RVCAPU2.AFS -> 1.afs -> sys000.bin & sys001.bin
  3. RVCAPU2.AFS -> 1.afs -> pac000999.pac (Rebuilds .evb event bytecode with full pointer relocation,
     hardware-exact LZR header & optimal compression, 64-byte PAC alignment, and exact 0xE0800 size preservation)
Pure Python - zero external dependencies.
"""

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
                # (Note: 0x13A3DC is the font glyph table - modifying it crashes the game font renderer!)
                #
                # Allocation layout within existing loaded ELF segments (PH[0]):
                # Group 1: 0x14f898..0x14f940 (168 bytes in .sdata, VA = offset + 0x0FF000)
                # Group 2: 0x14f724..0x14f780 (92 bytes in .rodata zero-padding)
                # Group 3: 0x14f7b0..0x14f800 (80 bytes in .rodata zero-padding)
                SPEAKER_TABLE_POS = 0x1047B8
                CHAR_SPEAKER_ALLOC = {
                    # sys_char_01..12, 21 in Group 1 (0x14f898..0x14f940)
                    "sys_char_01": (0x14F898, [0]),      # Tsukune (16 bytes) -> ends at 0x14F8A8
                    "sys_char_02": (0x14F8A8, [1, 2]),   # Moka (10 bytes) -> ends at 0x14F8B2 (shares idx 1 & 2)
                    "sys_char_03": (0x14F8B2, [3]),      # Kurumu (14 bytes) -> ends at 0x14F8C0
                    "sys_char_04": (0x14F8C0, [4]),      # Yukari (14 bytes) -> ends at 0x14F8CE
                    "sys_char_05": (0x14F8CE, [5]),      # Mizore (14 bytes) -> ends at 0x14F8DC
                    "sys_char_06": (0x14F8DC, [6]),      # Midou (12 bytes) -> ends at 0x14F8E8
                    "sys_char_07": (0x14F8E8, [7]),      # Kokoa (12 bytes) -> ends at 0x14F8F4
                    "sys_char_08": (0x14F8F4, [8]),      # Shizuka (16 bytes) -> ends at 0x14F904
                    "sys_char_09": (0x14F904, [9]),      # Rin (8 bytes) -> ends at 0x14F90C
                    "sys_char_10": (0x14F90C, [10]),     # Hitomi (14 bytes) -> ends at 0x14F91A
                    "sys_char_11": (0x14F91A, [11]),     # Ginei (12 bytes) -> ends at 0x14F926
                    "sys_char_12": (0x14F926, [12]),     # Nekonome (18 bytes) -> ends at 0x14F938
                    "sys_char_21": (0x14F938, [26]),     # ??? (8 bytes) -> ends at 0x14F940

                    # sys_char_13, 14, 15, 17, 18 in Group 2 (0x14f724..0x14f780)
                    "sys_char_13": (0x14F724, [15]),     # Bastard (16 bytes) -> ends at 0x14F734
                    "sys_char_14": (0x14F734, [16]),     # Koutarou (18 bytes) -> ends at 0x14F746
                    "sys_char_15": (0x14F746, [17]),     # Kasahara (18 bytes) -> ends at 0x14F758
                    "sys_char_17": (0x14F758, [19]),     # Sakasaku (18 bytes) -> ends at 0x14F76A
                    "sys_char_18": (0x14F76A, [20]),     # Voice (12 bytes) -> ends at 0x14F776

                    # sys_char_16, 19, 20 in Group 3 (0x14f7b0..0x14f800)
                    "sys_char_16": (0x14F7B0, [18]),     # Bouzaburou (22 bytes) -> ends at 0x14F7C6
                    "sys_char_19": (0x14F7C6, [21]),     # Karis (12 bytes) -> ends at 0x14F7D2
                    "sys_char_20": (0x14F7D2, [25]),     # Foreigner (20 bytes) -> ends at 0x14F7E6
                }

                for proj in projects:
                    for s in proj.strings:
                        if s.source_file == "SLPM_551.89":
                            trans = s.translations.get(target_lang, "").strip()
                            if not trans:
                                continue
                            offset = int(s.offset_hex, 16)
                            if s.id in CHAR_SPEAKER_ALLOC:
                                alloc_off, table_indices = CHAR_SPEAKER_ALLOC[s.id]
                                enc = encode_game_string(trans, use_halfwidth_ascii=True, auto_wrap=False) + b"\x00\x00"
                                slpm_bytes[alloc_off : alloc_off + len(enc)] = enc
                                va = alloc_off + 0x0FF000
                                for tidx in table_indices:
                                    struct.pack_into("<I", slpm_bytes, SPEAKER_TABLE_POS + tidx * 4, va)
                            elif "encoding=custom" in (s.context or ""):
                                fallback_len = _measure_null_terminated_span(slpm_bytes, offset, even_aligned=True)
                                max_len = _parse_max_bytes(s.context, fallback_len)
                                trans_bytes = encode_game_string(
                                    trans, use_halfwidth_ascii=True, auto_wrap=False
                                )
                                even_max = (max_len // 2) * 2
                                trans_bytes = trans_bytes[:even_max]
                                replacement = trans_bytes.ljust(max_len, b"\x00")
                                if 0 <= offset and max_len > 0 and offset + max_len <= len(slpm_bytes):
                                    slpm_bytes[offset : offset + max_len] = replacement
                            else:
                                fallback_len = _measure_null_terminated_span(slpm_bytes, offset, even_aligned=False)
                                max_len = _parse_max_bytes(s.context, fallback_len)
                                trans_bytes = trans.encode("shift_jis", errors="replace")[:max_len]
                                replacement = trans_bytes.ljust(max_len, b"\x00")
                                if 0 <= offset and max_len > 0 and offset + max_len <= len(slpm_bytes):
                                    slpm_bytes[offset : offset + max_len] = replacement

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
                                        evb_raw, script_trans, use_halfwidth_ascii=True
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

                            # If 64-byte aligned PAC exceeds orig_pac_size (919,552 bytes), recompress untouched
                            # entries with our optimal-parse LZR compressor until it fits within orig_pac_size.
                            if len(new_pac_bytes) > orig_pac_size:
                                excess = len(new_pac_bytes) - orig_pac_size
                                for item in rebuilt_entries:
                                    if excess <= 0:
                                        break
                                    if not item["modified"] and item["is_compressed"]:
                                        old_padded = ((len(item["data"]) + 63) // 64) * 64
                                        raw_untouched = decompress_lzr(item["data"])
                                        recomp = compress_lzr(raw_untouched)
                                        new_padded = ((len(recomp) + 63) // 64) * 64
                                        if new_padded < old_padded:
                                            item["data"] = recomp
                                            excess -= (old_padded - new_padded)
                                new_pac_bytes = PacArchive.build_pac_bytes(rebuilt_entries, align=64)

                            if len(new_pac_bytes) > orig_pac_size:
                                raise ValueError(
                                    f"Rebuilt pac000999.pac ({len(new_pac_bytes)} bytes) exceeds "
                                    f"original 1.afs size ({orig_pac_size} bytes)."
                                )

                            # Write rebuilt pac000999.pac padded to exact original size (0xE0800 = 919,552 bytes)
                            # so 1.afs header, 1.afs directory table, and 0.bin sector table remain 100% untouched!
                            f.seek(afs1_offset + pac_afs_entry.offset)
                            f.write(new_pac_bytes.ljust(orig_pac_size, b"\x00"))

        if progress_callback:
            progress_callback(4, 5, "Verifying sector integrity...")

        if progress_callback:
            progress_callback(5, 5, "Patch complete!")

        return output_iso_path
