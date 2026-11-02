"""
CRI Middleware AFS archive reader, extractor, and builder.
Pure Python - zero external dependencies.
"""

import os
import struct
from pathlib import Path
from typing import List, Dict, Optional

AFS_MAGIC = b"AFS\x00"
AFS_ALIGN = 2048


class AfsEntry:
    def __init__(self, index: int, name: str, offset: int, size: int):
        self.index = index
        self.name = name
        self.offset = offset
        self.size = size

    def __repr__(self):
        return f"<AfsEntry [{self.index:04d}] {self.name} offset=0x{self.offset:X} size={self.size}>"


class AfsArchive:
    def __init__(self, file_path_or_stream, base_offset: int = 0):
        self.base_offset = base_offset
        self.entries: List[AfsEntry] = []
        if isinstance(file_path_or_stream, (str, Path)):
            self.file_path = Path(file_path_or_stream)
            with open(self.file_path, "rb") as f:
                self._read_header(f)
        else:
            self.file_path = None
            self._read_header(file_path_or_stream)

    def _read_header(self, stream):
        stream.seek(self.base_offset)
        magic = stream.read(4)
        if magic != AFS_MAGIC:
            raise ValueError(f"Invalid AFS magic: {magic}")

        entry_count = struct.unpack("<I", stream.read(4))[0]
        raw_entries = []
        for i in range(entry_count):
            offset, size = struct.unpack("<II", stream.read(8))
            raw_entries.append({"index": i, "offset": offset, "size": size, "name": f"file_{i:04d}.bin"})

        # Check metadata directory descriptor
        self.dir_offset = 0
        self.dir_size = 0
        meta = stream.read(8)
        if len(meta) == 8:
            dir_offset, dir_size = struct.unpack("<II", meta)
            if 0 < dir_offset < 0xFFFFFFFF:
                self.dir_offset = dir_offset
                self.dir_size = dir_size
                stream.seek(self.base_offset + dir_offset)
                for i in range(entry_count):
                    rec = stream.read(48)
                    if len(rec) < 48:
                        break
                    fname = rec[:32].split(b"\x00")[0].decode("ascii", errors="ignore").strip()
                    if fname:
                        raw_entries[i]["name"] = fname

        for r in raw_entries:
            self.entries.append(AfsEntry(r["index"], r["name"], r["offset"], r["size"]))

    def extract_all(self, output_dir: Path | str, stream=None) -> int:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        should_close = False
        if stream is None:
            if not self.file_path:
                raise ValueError("No stream or file path provided for extraction.")
            stream = open(self.file_path, "rb")
            should_close = True

        try:
            for entry in self.entries:
                # Sanitize filename
                clean_name = entry.name.replace("\\", "/").lstrip("/")
                out_file = output_dir / clean_name
                out_file.parent.mkdir(parents=True, exist_ok=True)

                stream.seek(self.base_offset + entry.offset)
                with open(out_file, "wb") as dst:
                    remaining = entry.size
                    chunk_size = 1024 * 1024
                    while remaining > 0:
                        n = min(remaining, chunk_size)
                        buf = stream.read(n)
                        if not buf:
                            break
                        dst.write(buf)
                        remaining -= len(buf)
        finally:
            if should_close:
                stream.close()

        return len(self.entries)

    @staticmethod
    def build_afs(file_list: List[Dict[str, any]], output_afs_path: Path | str):
        """
        Builds a new .AFS archive from a list of files:
        [{'name': 'relative/path.bin', 'data': bytes or 'path': Path}, ...]
        Aligned to AFS_ALIGN (2048) sectors, with filename directory descriptor.
        """
        output_afs_path = Path(output_afs_path)
        output_afs_path.parent.mkdir(parents=True, exist_ok=True)
        count = len(file_list)

        # Header size: 8 bytes + count * 8 bytes + 8 bytes metadata info = 16 + count * 8
        header_len = 8 + (count * 8) + 8
        # First file starts at first 2048-byte aligned sector
        first_file_offset = ((header_len + AFS_ALIGN - 1) // AFS_ALIGN) * AFS_ALIGN

        offsets_and_sizes = []
        current_offset = first_file_offset

        # Precalculate layout
        for item in file_list:
            size = len(item["data"]) if "data" in item else Path(item["path"]).stat().st_size
            offsets_and_sizes.append((current_offset, size))
            # Align next file to AFS_ALIGN
            current_offset += ((size + AFS_ALIGN - 1) // AFS_ALIGN) * AFS_ALIGN

        dir_offset = current_offset
        dir_size = count * 48

        with open(output_afs_path, "wb") as f:
            # Write header
            f.write(AFS_MAGIC)
            f.write(struct.unpack("<I", struct.pack("<I", count))[0].to_bytes(4, "little"))

            # Write file entries
            for off, sz in offsets_and_sizes:
                f.write(struct.pack("<II", off, sz))

            # Write directory descriptor info
            f.write(struct.pack("<II", dir_offset, dir_size))

            # Pad to first file
            pad_len = first_file_offset - f.tell()
            if pad_len > 0:
                f.write(b"\x00" * pad_len)

            # Write file data
            for idx, item in enumerate(file_list):
                off, sz = offsets_and_sizes[idx]
                f.seek(off)
                if "data" in item:
                    f.write(item["data"])
                else:
                    with open(item["path"], "rb") as src:
                        chunk_size = 1024 * 1024
                        while True:
                            buf = src.read(chunk_size)
                            if not buf:
                                break
                            f.write(buf)

            # Seek to dir_offset and write 48-byte filename records
            f.seek(dir_offset)
            for idx, item in enumerate(file_list):
                name = item["name"].replace("\\", "/")
                name_bytes = name.encode("ascii", errors="ignore")[:31]
                rec = bytearray(48)
                rec[:len(name_bytes)] = name_bytes
                # Directory record layout:
                # 0..31: filename
                # 32..43: timestamp (year uint16, month, day, hour, min, sec, etc.)
                # 44..47: file length
                sz = offsets_and_sizes[idx][1]
                struct.pack_into("<I", rec, 44, sz)
                f.write(rec)

            # Pad end of AFS to 2048 boundary
            total_end = f.tell()
            end_pad = ((total_end + AFS_ALIGN - 1) // AFS_ALIGN) * AFS_ALIGN - total_end
            if end_pad > 0:
                f.write(b"\x00" * end_pad)
