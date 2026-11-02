"""
HuneX PAC archive (.pac) unpacker and builder for Rosario + Vampire PS2.
Pure Python - zero external dependencies.
"""

import struct
from pathlib import Path
from typing import List, Dict, Optional


class PacEntry:
    def __init__(self, index: int, name: str, flag: int, uncomp_size: int, comp_size: int, offset: int, data: Optional[bytes] = None):
        self.index = index
        self.name = name
        self.flag = flag
        self.uncomp_size = uncomp_size
        self.comp_size = comp_size
        self.offset = offset
        self.data = data

    @property
    def is_compressed(self) -> bool:
        # Flag 0x00010300 is LZR compressed; flag 0x00000300 or 0x00000200 is uncompressed
        return bool(self.flag & 0x00010000)

    def __repr__(self):
        comp_str = "COMP" if self.is_compressed else "RAW"
        return f"<PacEntry [{self.index:04d}] {self.name:<16} {comp_str} offset=0x{self.offset:X} size={self.uncomp_size}>"


class PacArchive:
    def __init__(self, data_or_path: bytes | Path | str):
        if isinstance(data_or_path, (str, Path)):
            with open(data_or_path, "rb") as f:
                self.data = f.read()
        else:
            self.data = data_or_path
        self.entries: List[PacEntry] = []
        self._parse()

    def _parse(self):
        if len(self.data) < 16:
            return
        # First 4 bytes: uint16 at [2:4] contains entry count
        count = struct.unpack("<H", self.data[2:4])[0]
        if count == 0 or count > 10000:
            return

        table_start = 16
        for i in range(count):
            entry_bytes = self.data[table_start + i * 32 : table_start + (i + 1) * 32]
            if len(entry_bytes) < 32:
                break
            flag, uncomp_sz, comp_sz, offset = struct.unpack("<IIII", entry_bytes[:16])
            name = entry_bytes[16:32].split(b"\x00")[0].decode("ascii", errors="ignore").strip()

            actual_size = comp_sz if (flag & 0x00010000) and comp_sz > 0 else uncomp_sz
            file_data = self.data[offset : offset + actual_size]

            self.entries.append(PacEntry(
                index=i,
                name=name,
                flag=flag,
                uncomp_size=uncomp_sz,
                comp_size=comp_sz,
                offset=offset,
                data=file_data
            ))

    def extract_all(self, output_dir: Path | str) -> int:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for entry in self.entries:
            out_file = output_dir / entry.name
            with open(out_file, "wb") as f:
                f.write(entry.data)
        return len(self.entries)

    @staticmethod
    def build_pac_bytes(entries: List[Dict[str, any]], align: int = 64) -> bytes:
        """
        Builds a valid .pac container in memory and returns its bytes.
        entries: list of dicts:
          {'name': 'e100000.evb', 'data': bytes, 'is_compressed': bool (optional), 'uncomp_size': int (optional), 'flag': int (optional)}
        align: byte alignment for entry payloads (64 bytes in all original PS2 PAC archives).
        """
        count = len(entries)
        header = bytearray(16)
        struct.pack_into("<H", header, 2, count)

        table_size = 16 + (count * 32)
        first_offset = ((table_size + 63) // 64) * 64

        table_records = []
        payloads = []
        current_offset = first_offset

        for item in entries:
            data = item["data"]
            name = item["name"]
            is_comp = item.get("is_compressed", False)

            if is_comp:
                flag = item.get("flag", 0x00010300) | 0x00010000
                comp_sz = len(data)
                uncomp_sz = item.get("uncomp_size", comp_sz)
            else:
                flag = item.get("flag", 0x00000300) & ~0x00010000
                uncomp_sz = len(data)
                comp_sz = 0

            rec = bytearray(32)
            struct.pack_into("<IIII", rec, 0, flag, uncomp_sz, comp_sz, current_offset)
            name_bytes = name.encode("ascii", errors="ignore")[:15]
            rec[16 : 16 + len(name_bytes)] = name_bytes

            table_records.append(rec)
            payloads.append(data)

            padded_size = ((len(data) + align - 1) // align) * align
            current_offset += padded_size

        out = bytearray()
        out.extend(header)
        for rec in table_records:
            out.extend(rec)

        pad = first_offset - len(out)
        if pad > 0:
            out.extend(b"\x00" * pad)

        for data in payloads:
            out.extend(data)
            p = ((len(data) + align - 1) // align) * align - len(data)
            if p > 0:
                out.extend(b"\x00" * p)

        return bytes(out)

    @staticmethod
    def build_pac(entries: List[Dict[str, any]], output_pac_path: Path | str, align: int = 64):
        output_pac_path = Path(output_pac_path)
        output_pac_path.parent.mkdir(parents=True, exist_ok=True)
        pac_bytes = PacArchive.build_pac_bytes(entries, align=align)
        with open(output_pac_path, "wb") as f:
            f.write(pac_bytes)

