"""
LZR Decompression and .evb Event Bytecode Parser/Rebuilder for
Rosario + Vampire Capu 2: Koi to Yume no Rhapsodia (PS2, SLPM_551.89).

Pure Python - zero external dependencies.
"""

import re
import struct
from typing import Dict, List, Optional, Tuple
from font_mapper import decode_game_string, encode_game_string

# Jump opcodes and the byte offset inside their packet where the uint16 target offset lives
JUMP_OPCODES: Dict[int, int] = {
    0x0003: 4,
    0x0004: 4,
    0x0008: 4,
    0x000E: 4,
    0x0010: 4,
    0x0407: 6,
    0x041E: 6,
    0x041F: 6,
    0x0431: 4,
    0x0433: 8,
}


def decompress_lzr(data: bytes) -> bytes:
    """
    Decompresses a buffer starting with b'LZR\\x00' (reverse-engineered from
    VA 0x00145458 / 0x00145208 in SLPM_551.89).
    """
    if len(data) < 16 or data[:4] != b"LZR\x00":
        return data

    f1, f2, decomp_size = struct.unpack("<III", data[4:16])
    steps = f1 // 2
    ctrl_pos = 16
    data_pos = 16 + ((f1 + 7) >> 3)
    mask = 0xC0
    out = bytearray()

    for _ in range(steps):
        t6 = data[ctrl_pos] & mask
        if t6 == 0:
            # 00: 1 literal byte
            out.append(data[data_pos])
            data_pos += 1
        elif t6 in (0x01, 0x04, 0x10, 0x40):
            # 01: N literal bytes
            count = data[data_pos]
            data_pos += 1
            out.extend(data[data_pos : data_pos + count])
            data_pos += count
        elif t6 in (0x02, 0x08, 0x20, 0x80):
            # 10: RLE repeat
            count = data[data_pos]
            val = data[data_pos + 1]
            data_pos += 2
            out.extend([val] * count)
        else:
            # 11: LZ backreference
            b0 = data[data_pos]
            b1 = data[data_pos + 1]
            data_pos += 2
            dist = (b0 << 4) | (b1 >> 4)
            length = b1 & 0x0F
            for _ in range(length):
                out.append(out[-dist])

        mask >>= 2
        if mask == 0:
            mask = 0xC0
            ctrl_pos += 1

    return bytes(out)


def _build_lzr(ops: List[Tuple[int, int, any]], n: int) -> bytes:
    """
    Serializes a list of LZR ops into a buffer with the exact header layout used by
    the original HuneX files:
      0x00 'LZR\\0'
      0x04 u32 control bit count (2 bits per op)
      0x08 u32 length of the data body (bytes AFTER the control bitfield)
      0x0C u32 decompressed size
    """
    f1 = len(ops) * 2
    ctrl_len = (f1 + 7) >> 3
    ctrl = bytearray(ctrl_len)
    mask_shifts = [6, 4, 2, 0]
    body = bytearray()
    for i, (t, a1, a2) in enumerate(ops):
        if t != 0:
            ctrl[i // 4] |= t << mask_shifts[i % 4]
        if t == 0:
            body.append(a1)
        elif t == 1:
            body.append(a1)
            body.extend(a2)
        elif t == 2:
            body.append(a1)
            body.append(a2)
        else:
            body.append((a1 >> 4) & 0xFF)
            body.append(((a1 & 0x0F) << 4) | (a2 & 0x0F))
    header = struct.pack("<4sIII", b"LZR\x00", f1, len(body), n)
    return bytes(header + ctrl + body)


def compress_lzr(raw: bytes) -> bytes:
    """
    Optimal-parse LZR compressor (dynamic programming over bit cost).
    Usually produces output equal to or smaller than the original HuneX tool.
    Op costs: literal 10 bits, N-literal run 10+8N bits, RLE 18 bits, LZ 18 bits.
    """
    from collections import deque

    n = len(raw)
    if n == 0:
        return struct.pack("<4sIII", b"LZR\x00", 0, 0, 0)

    INF = float("inf")
    cost = [INF] * (n + 1)
    choice: List[Optional[Tuple[int, int, int]]] = [None] * (n + 1)
    cost[0] = 0

    run = [1] * n
    for i in range(n - 2, -1, -1):
        if raw[i] == raw[i + 1]:
            run[i] = run[i + 1] + 1

    chains: Dict[bytes, List[int]] = {}
    lit_window: deque = deque()  # (j, cost[j] - 8*j), increasing key

    for i in range(n + 1):
        # Finalize cost[i] with the best literal run ending at i (length 2..255)
        j = i - 2
        if j >= 0 and cost[j] < INF:
            key = cost[j] - 8 * j
            while lit_window and lit_window[-1][1] >= key:
                lit_window.pop()
            lit_window.append((j, key))
        while lit_window and lit_window[0][0] < i - 255:
            lit_window.popleft()
        if lit_window:
            jb, kb = lit_window[0]
            c = kb + 10 + 8 * i
            if c < cost[i]:
                cost[i] = c
                choice[i] = (1, i - jb, 0)
        if i == n:
            break

        base = cost[i]
        # Single literal
        if base + 10 < cost[i + 1]:
            cost[i + 1] = base + 10
            choice[i + 1] = (0, 1, 0)
        # RLE
        r = min(255, run[i])
        if r >= 2:
            c = base + 18
            for L in range(2, r + 1):
                if c < cost[i + L]:
                    cost[i + L] = c
                    choice[i + L] = (2, L, raw[i])
        # LZ backreference (dist 1..4095, len 3..15)
        if i + 3 <= n:
            key3 = raw[i : i + 3]
            lst = chains.get(key3)
            if lst:
                max_l = min(15, n - i)
                best_len = 0
                best_dist = 0
                depth = 0
                for cand in reversed(lst):
                    d = i - cand
                    if d > 4095 or depth >= 256:
                        break
                    depth += 1
                    l = 3
                    while l < max_l and raw[cand + l] == raw[i + l]:
                        l += 1
                    if l > best_len:
                        best_len = l
                        best_dist = d
                        if l == max_l:
                            break
                if best_len >= 3:
                    c = base + 18
                    for L in range(3, best_len + 1):
                        if c < cost[i + L]:
                            cost[i + L] = c
                            choice[i + L] = (3, L, best_dist)
            chains.setdefault(key3, []).append(i)

    # Backtrack
    ops_rev = []
    pos = n
    while pos > 0:
        t, L, p = choice[pos]
        start = pos - L
        if t == 0:
            ops_rev.append((0, raw[start], 0))
        elif t == 1:
            ops_rev.append((1, L, raw[start:pos]))
        elif t == 2:
            ops_rev.append((2, L, p))
        else:
            ops_rev.append((3, p, L))
        pos = start
    ops_rev.reverse()
    return _build_lzr(ops_rev, n)


def compress_lzr_greedy(raw: bytes) -> bytes:
    """
    Compresses raw bytes into a valid LZR stream using all 4 hardware opcodes:
      - 00: 1 literal byte
      - 01: N literal bytes (2..255)
      - 10: RLE repeat (4..255 of same byte)
      - 11: LZ77 backreference (dist 1..4095, length 3..15)
    """
    n = len(raw)
    if n == 0:
        return struct.pack("<4sIII", b"LZR\x00", 0, 16, 0)

    head: Dict[bytes, int] = {}
    prev = [-1] * n

    def add_pos(p: int):
        if p + 3 <= n:
            key = raw[p : p + 3]
            prev[p] = head.get(key, -1)
            head[key] = p

    ops: List[Tuple[int, int, any]] = []
    lit_buf = bytearray()

    def flush_lits():
        nonlocal lit_buf
        if not lit_buf:
            return
        mv = bytes(lit_buf)
        lit_buf.clear()
        p = 0
        while p < len(mv):
            rem = len(mv) - p
            if rem == 1:
                ops.append((0, mv[p], 0))
                p += 1
            else:
                chunk = mv[p : p + 255]
                ops.append((1, len(chunk), chunk))
                p += len(chunk)

    pos = 0
    while pos < n:
        b = raw[pos]
        rle_len = 1
        max_rle = min(255, n - pos)
        while rle_len < max_rle and raw[pos + rle_len] == b:
            rle_len += 1

        best_len = 0
        best_dist = 0
        if pos + 3 <= n:
            key = raw[pos : pos + 3]
            cand = head.get(key, -1)
            max_l = min(15, n - pos)
            chain = 64
            while cand != -1 and pos - cand <= 4095 and chain > 0:
                chain -= 1
                if best_len < max_l and raw[cand + best_len] == raw[pos + best_len]:
                    l = 3
                    while l < max_l and raw[cand + l] == raw[pos + l]:
                        l += 1
                    if l > best_len:
                        best_len = l
                        best_dist = pos - cand
                        if best_len == 15:
                            break
                cand = prev[cand]

        if rle_len >= 4 and rle_len >= best_len:
            flush_lits()
            ops.append((2, rle_len, b))
            for k in range(rle_len):
                add_pos(pos + k)
            pos += rle_len
        elif best_len >= 3:
            flush_lits()
            ops.append((3, best_dist, best_len))
            for k in range(best_len):
                add_pos(pos + k)
            pos += best_len
        else:
            lit_buf.append(b)
            add_pos(pos)
            pos += 1

    flush_lits()
    return _build_lzr(ops, n)


def parse_evb_commands(evb: bytes) -> List[Tuple[int, int, bytes]]:
    """
    Parses an uncompressed .evb buffer into a list of (offset, opcode, raw_bytes).
    """
    cmds = []
    pos = 0
    while pos + 2 <= len(evb):
        op = struct.unpack("<h", evb[pos : pos + 2])[0]
        if op == -1:
            cmds.append((pos, op, evb[pos : pos + 2]))
            pos += 2
        elif op < 0:
            plen = struct.unpack("<H", evb[pos + 2 : pos + 4])[0]
            cmds.append((pos, op, evb[pos : pos + plen]))
            pos += plen
        else:
            plen = evb[pos + 2]
            if plen == 0:
                plen = 2
            cmds.append((pos, op, evb[pos : pos + plen]))
            pos += plen
    return cmds


# ---------------------------------------------------------------------------------------------
# Engine text-length limit (reverse-engineered from SLPM_551.89)
#
# The script handlers for 0xFFFE (dialogue, VA 0x0010B8D0), 0xFFFD (choices, VA 0x0010BB10) and
# 0xFFFC (special prompts, VA 0x0010BF20) all push the displayed text into the backlog via
# VA 0x00108628. The length argument is computed from the packet's length field and then
# truncated + sign-extended to 8 bits (`sll a3,a3,24 / sra a3,a3,24`) before being handed to
# memcpy (VA 0x001E799C) targeting a 131-byte backlog slot (256 slots x 140 bytes).
#
#   0xFFFE : len = (u8)pkt[2]        - 16
#   0xFFFD : len = (u8)entry[2]      - 16          (per choice entry)
#   0xFFFC : len = pkt_len - rel[0]                (all entries concatenated, 256-byte stack buf)
#
# Any text payload (string + NUL + padding) of 128 bytes or more turns into a negative length,
# i.e. a ~4 GB memcpy that wipes RAM and crashes PCSX2 with a random PC
# ("Jump to unmapped recLUT page"). The original Japanese scripts never exceed 100 bytes.
# ---------------------------------------------------------------------------------------------
MAX_SCRIPT_TEXT_BYTES = 127
MAX_SPECIAL_PROMPT_ENTRIES = 3  # 0xFFFC handler clamps the entry count to 3


def _pad_null_terminated(encoded: bytes, align: int = 2) -> bytes:
    """
    Appends a NUL terminator and pads with 0x00 up to `align` byte alignment,
    matching the original HuneX .evb compiler layout.
    """
    total = len(encoded) + 1
    rem = total % align
    pad_len = (align - rem) if rem != 0 else 0
    return encoded + b"\x00" * (1 + pad_len)


def _split_trailing_tags(text: str) -> Tuple[str, str]:
    """Splits trailing control tags such as '[B:19]' or '[B:19][B:01]' off the end of `text`."""
    suffix = ""
    while True:
        m = re.search(r"\[(?:B:[0-9A-Fa-f]{2}|C:\d+)\]$", text)
        if not m:
            break
        suffix = m.group(0) + suffix
        text = text[: m.start()]
    return text, suffix


def encode_script_text(
    text: str,
    max_payload: int,
    align: int = 2,
    use_halfwidth_ascii: bool = True,
    auto_wrap: bool = False,
    max_cols: int = 18,
    warnings_out: Optional[List[str]] = None,
    label: str = "",
) -> bytes:
    """
    Encodes `text` into a NUL-terminated, padded payload that is guaranteed to be <= max_payload bytes.
    Strategy:
      1. Normal encoding (half-width 0x8020 spaces).
      2. Compact encoding (single-byte 0x20 spaces, as used by the original scripts).
      3. Last resort: drop trailing words and append '...' (emits a warning so the line can be shortened).
    """
    def build(t: str, compact: bool) -> bytes:
        enc = encode_game_string(
            t, use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=auto_wrap, max_cols=max_cols,
            compact_spaces=compact,
        )
        return _pad_null_terminated(enc, align=align)

    payload = build(text, False)
    if len(payload) <= max_payload:
        return payload
    payload = build(text, True)
    if len(payload) <= max_payload:
        return payload

    body, suffix = _split_trailing_tags(text)
    words = body.replace("\n", " ").split()
    while words:
        words.pop()
        candidate = " ".join(words).rstrip(" ,;:.-") + "..." + suffix
        payload = build(candidate, True)
        if len(payload) <= max_payload:
            break
    else:
        payload = _pad_null_terminated(b"", align=align)
    if warnings_out is not None:
        warnings_out.append(
            f"{label}: text too long for the engine limit ({max_payload} bytes) and was truncated. "
            f"Please shorten it: {text!r}"
        )
    return payload


def extract_evb_strings(evb: bytes, script_name: str = "") -> List[Dict[str, any]]:
    """
    Extracts all text strings (0xFFFE dialogue, 0xFFFD choices, 0xFFFC special, 0x0412 banners)
    from an uncompressed .evb bytecode buffer.
    Returns a list of dicts with keys:
      'offset_hex': str (e.g. '0x0044' or '0x0530:0')
      'original_ja': str
      'context': str
    """
    cmds = parse_evb_commands(evb)
    results = []
    for pos, op, cmd_bytes in cmds:
        if op == -2:  # 0xFFFE: Dialogue message
            voice_id = struct.unpack("<i", cmd_bytes[4:8])[0]
            speaker = struct.unpack("<h", cmd_bytes[10:12])[0]
            ja = decode_game_string(cmd_bytes[16:])
            if ja.strip():
                results.append({
                    "offset_hex": f"0x{pos:04X}",
                    "original_ja": ja,
                    "context": f"Dialogue ({script_name} spk={speaker}, voice={voice_id})",
                })
        elif op == -3:  # 0xFFFD: Branching choice menu
            cnt = struct.unpack("<H", cmd_bytes[4:6])[0]
            for c_idx in range(cnt):
                rel = struct.unpack("<I", cmd_bytes[8 + c_idx * 4 : 12 + c_idx * 4])[0]
                ja = decode_game_string(cmd_bytes[rel + 16 :])
                if ja.strip():
                    results.append({
                        "offset_hex": f"0x{pos:04X}:{c_idx}",
                        "original_ja": ja,
                        "context": f"Choice {c_idx + 1}/{cnt} ({script_name})",
                    })
        elif op == -4:  # 0xFFFC: Multi-line special prompt
            cnt = struct.unpack("<H", cmd_bytes[4:6])[0]
            for c_idx in range(cnt):
                rel = struct.unpack("<I", cmd_bytes[8 + c_idx * 4 : 12 + c_idx * 4])[0]
                ja = decode_game_string(cmd_bytes[rel:])
                if ja.strip():
                    results.append({
                        "offset_hex": f"0x{pos:04X}:{c_idx}",
                        "original_ja": ja,
                        "context": f"Special prompt {c_idx + 1}/{cnt} ({script_name})",
                    })
        elif op == 0x0412:  # Location / map banner
            ja = decode_game_string(cmd_bytes[12:])
            if ja.strip():
                results.append({
                    "offset_hex": f"0x{pos:04X}",
                    "original_ja": ja,
                    "context": f"Location banner ({script_name})",
                })
    return results


def pad_with_target_mod4(enc: bytes, target_mod4: int, header_len: int) -> bytes:
    """
    Appends null padding so that (header_len + len(payload)) % 4 == target_mod4.
    Always includes at least one null terminator (0x00).
    """
    base_len = header_len + len(enc) + 1
    pad = (target_mod4 - (base_len % 4)) % 4
    return enc + b"\x00" * (1 + pad)


def rebuild_evb(evb: bytes, translations: Dict[str, str], use_halfwidth_ascii: bool = True, max_dialogue_bytes: int = 124) -> bytes:
    """
    Rebuilds an uncompressed .evb bytecode buffer with translated strings.
    `translations` maps `offset_hex` (e.g. '0x0044' or '0x0530:0') to the translated string.
    Automatically recalculates packet lengths and relocates all jump/branch target offsets.
    Guarantees:
      1. Every modified packet preserves its exact original length parity mod 4, preventing
         MIPS unaligned memory access exceptions in the game engine.
      2. Every dialogue string is strictly capped <= 124 bytes so the PS2 backlog length
         calculation (signed 8-bit) never goes negative and triggers a 4 GB RAM wipe.
    """
    if not translations:
        return evb

    cmds = parse_evb_commands(evb)
    old_to_new: Dict[int, int] = {}
    new_cmds: List[Tuple[int, int, bytearray]] = []
    curr_new_offset = 0

    for pos, op, cmd_bytes in cmds:
        old_to_new[pos] = curr_new_offset
        off_key = f"0x{pos:04X}"
        orig_len = len(cmd_bytes)
        target_mod4 = orig_len % 4

        if op == -2 and off_key in translations and translations[off_key].strip():
            trans_text = translations[off_key].strip()
            # Preserve trailing control bytes like [B:19] or [B:19][B:01] from original if not in translation
            orig_ja = decode_game_string(cmd_bytes[16:])
            for suffix in ("[B:19][B:01]", "[B:19]"):
                if orig_ja.endswith(suffix) and not trans_text.endswith(suffix):
                    trans_text += suffix
                    break

            # Use compact space encoding (single-byte 0x20, as used by original scripts) to save space
            enc = encode_game_string(trans_text, use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=True, max_cols=34, compact_spaces=True)
            payload = pad_with_target_mod4(enc, target_mod4, header_len=16)

            # Safety fallback: truncate words if exceeding max_dialogue_bytes
            if len(payload) > max_dialogue_bytes:
                body, suffix_tag = _split_trailing_tags(trans_text)
                words = body.replace("\n", " ").split()
                while words and len(payload) > max_dialogue_bytes:
                    words.pop()
                    cand = " ".join(words).rstrip(" ,;:.-") + "..." + suffix_tag
                    enc = encode_game_string(cand, use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=True, max_cols=34, compact_spaces=True)
                    payload = pad_with_target_mod4(enc, target_mod4, header_len=16)

            new_pkt = bytearray(cmd_bytes[:16]) + payload
            struct.pack_into("<H", new_pkt, 2, len(new_pkt))
            new_cmds.append((pos, op, new_pkt))
            curr_new_offset += len(new_pkt)

        elif op == -3:
            cnt = struct.unpack("<H", cmd_bytes[4:6])[0]
            any_changed = any(f"0x{pos:04X}:{c_idx}" in translations and translations[f"0x{pos:04X}:{c_idx}"].strip() for c_idx in range(cnt))
            if not any_changed:
                new_pkt = bytearray(cmd_bytes)
            else:
                header_size = 8 + cnt * 4
                new_pkt = bytearray(cmd_bytes[:header_size])
                for c_idx in range(cnt):
                    rel = struct.unpack("<I", cmd_bytes[8 + c_idx * 4 : 12 + c_idx * 4])[0]
                    entry_hdr = bytearray(cmd_bytes[rel : rel + 16])
                    c_key = f"0x{pos:04X}:{c_idx}"
                    if c_key in translations and translations[c_key].strip():
                        enc = encode_game_string(translations[c_key].strip(), use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=False, compact_spaces=True)
                        str_payload = pad_with_target_mod4(enc, target_mod4=0, header_len=16)
                    else:
                        next_rel = struct.unpack("<I", cmd_bytes[8 + (c_idx + 1) * 4 : 12 + (c_idx + 1) * 4])[0] if c_idx + 1 < cnt else len(cmd_bytes)
                        str_payload = cmd_bytes[rel + 16 : next_rel]
                    new_rel = len(new_pkt)
                    struct.pack_into("<I", new_pkt, 8 + c_idx * 4, new_rel)
                    sub_len = len(entry_hdr) + len(str_payload)
                    struct.pack_into("<H", entry_hdr, 2, sub_len)
                    new_pkt.extend(entry_hdr)
                    new_pkt.extend(str_payload)
                if len(new_pkt) % 4 != target_mod4:
                    pad = (target_mod4 - (len(new_pkt) % 4)) % 4
                    new_pkt.extend(b"\x00" * pad)
                struct.pack_into("<H", new_pkt, 2, len(new_pkt))
            new_cmds.append((pos, op, new_pkt))
            curr_new_offset += len(new_pkt)

        elif op == -4:
            cnt = struct.unpack("<H", cmd_bytes[4:6])[0]
            any_changed = any(f"0x{pos:04X}:{c_idx}" in translations and translations[f"0x{pos:04X}:{c_idx}"].strip() for c_idx in range(cnt))
            if not any_changed:
                new_pkt = bytearray(cmd_bytes)
            else:
                header_size = 8 + cnt * 4
                new_pkt = bytearray(cmd_bytes[:header_size])
                for c_idx in range(cnt):
                    rel = struct.unpack("<I", cmd_bytes[8 + c_idx * 4 : 12 + c_idx * 4])[0]
                    c_key = f"0x{pos:04X}:{c_idx}"
                    if c_key in translations and translations[c_key].strip():
                        enc = encode_game_string(translations[c_key].strip(), use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=False, compact_spaces=True)
                        str_payload = pad_with_target_mod4(enc, target_mod4=0, header_len=0)
                    else:
                        next_rel = struct.unpack("<I", cmd_bytes[8 + (c_idx + 1) * 4 : 12 + (c_idx + 1) * 4])[0] if c_idx + 1 < cnt else len(cmd_bytes)
                        str_payload = cmd_bytes[rel:next_rel]
                    new_rel = len(new_pkt)
                    struct.pack_into("<I", new_pkt, 8 + c_idx * 4, new_rel)
                    new_pkt.extend(str_payload)
                if len(new_pkt) % 4 != target_mod4:
                    pad = (target_mod4 - (len(new_pkt) % 4)) % 4
                    new_pkt.extend(b"\x00" * pad)
                struct.pack_into("<H", new_pkt, 2, len(new_pkt))
            new_cmds.append((pos, op, new_pkt))
            curr_new_offset += len(new_pkt)

        elif op == 0x0412 and off_key in translations and translations[off_key].strip():
            enc = encode_game_string(translations[off_key].strip(), use_halfwidth_ascii=use_halfwidth_ascii, auto_wrap=False, compact_spaces=True)
            str_payload = pad_with_target_mod4(enc, target_mod4, header_len=12)
            new_pkt = bytearray(cmd_bytes[:12]) + str_payload
            struct.pack_into("<H", new_pkt, 2, len(new_pkt))
            new_cmds.append((pos, op, new_pkt))
            curr_new_offset += len(new_pkt)

        else:
            new_pkt = bytearray(cmd_bytes)
            new_cmds.append((pos, op, new_pkt))
            curr_new_offset += len(new_pkt)

    old_to_new[len(evb)] = curr_new_offset

    # Second pass: relocate all jump/branch targets
    out = bytearray()
    for pos, op, new_pkt in new_cmds:
        if op in JUMP_OPCODES:
            field_off = JUMP_OPCODES[op]
            old_target = struct.unpack("<H", new_pkt[field_off : field_off + 2])[0]
            if old_target in old_to_new:
                new_target = old_to_new[old_target]
                struct.pack_into("<H", new_pkt, field_off, new_target)
        out.extend(new_pkt)

    return bytes(out)
