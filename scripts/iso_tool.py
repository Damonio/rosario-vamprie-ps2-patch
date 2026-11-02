"""
ISO 9660 parser, reader, and patcher for PlayStation 2 disc images.
Pure Python - zero external dependencies.
"""

import os
import struct
from pathlib import Path
from typing import Dict, Optional, Tuple

SECTOR_SIZE = 2048
PVD_SECTOR = 16


class IsoEntry:
    def __init__(self, name: str, lba: int, size: int, is_dir: bool):
        self.name = name
        self.lba = lba
        self.offset = lba * SECTOR_SIZE
        self.size = size
        self.is_dir = is_dir

    def __repr__(self):
        type_str = "DIR" if self.is_dir else "FILE"
        return f"<IsoEntry {self.name} [{type_str}] offset=0x{self.offset:X} size={self.size}>"


class IsoHandler:
    def __init__(self, iso_path: Path | str):
        self.iso_path = Path(iso_path)
        self.entries: Dict[str, IsoEntry] = {}
        if self.iso_path.exists():
            self._parse()

    def _parse(self):
        with open(self.iso_path, "rb") as f:
            # Sector 16: Primary Volume Descriptor (PVD)
            f.seek(PVD_SECTOR * SECTOR_SIZE)
            pvd = f.read(SECTOR_SIZE)
            if pvd[1:6] != b"CD001":
                raise ValueError(f"'{self.iso_path}' is not a standard ISO 9660 image.")

            # Root directory record at byte offset 156 (34 bytes long)
            root_rec = pvd[156:156 + 34]
            root_lba = struct.unpack("<I", root_rec[2:6])[0]
            root_size = struct.unpack("<I", root_rec[10:14])[0]

            # Read root directory entries
            f.seek(root_lba * SECTOR_SIZE)
            dir_data = f.read(root_size)

            pos = 0
            while pos < len(dir_data):
                rec_len = dir_data[pos]
                if rec_len == 0:
                    pos = ((pos // SECTOR_SIZE) + 1) * SECTOR_SIZE
                    continue

                rec = dir_data[pos:pos + rec_len]
                pos += rec_len

                lba = struct.unpack("<I", rec[2:6])[0]
                data_len = struct.unpack("<I", rec[10:14])[0]
                flags = rec[25]
                name_len = rec[32]
                name = rec[33:33 + name_len].decode("ascii", errors="replace").split(";")[0]

                if name and name not in ("\x00", "\x01"):
                    entry = IsoEntry(name, lba, data_len, bool(flags & 2))
                    self.entries[name] = entry

    def extract_file(self, internal_name: str, output_path: Path | str) -> bool:
        if internal_name not in self.entries:
            return False
        entry = self.entries[internal_name]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.iso_path, "rb") as src, open(output_path, "wb") as dst:
            src.seek(entry.offset)
            remaining = entry.size
            chunk_size = 1024 * 1024
            while remaining > 0:
                n = min(remaining, chunk_size)
                buf = src.read(n)
                if not buf:
                    break
                dst.write(buf)
                remaining -= len(buf)
        return True

    def patch_file_in_place(self, internal_name: str, replacement_data: bytes) -> bool:
        """
        Replaces the file content in-place within the ISO if the new data fits inside original sector allocation.
        """
        if internal_name not in self.entries:
            return False
        entry = self.entries[internal_name]
        max_bytes = ((entry.size + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE
        if len(replacement_data) > max_bytes:
            raise ValueError(f"Replacement data ({len(replacement_data)} bytes) exceeds allocated space ({max_bytes} bytes).")

        with open(self.iso_path, "r+b") as f:
            f.seek(entry.offset)
            f.write(replacement_data)
            # Pad sector with zeros if smaller
            pad = max_bytes - len(replacement_data)
            if pad > 0:
                f.write(b"\x00" * pad)
        return True
