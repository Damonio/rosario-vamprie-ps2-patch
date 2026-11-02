import struct

REGS = [
    "zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
    "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
    "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
    "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"
]

def disasm_mips(word, va):
    op = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    sa = (word >> 6) & 0x1F
    fn = word & 0x3F
    imm = word & 0xFFFF
    simm = imm if imm < 0x8000 else imm - 0x10000
    target = (word & 0x03FFFFFF) << 2
    
    if word == 0: return "nop"
    if op == 0: # SPECIAL
        if fn == 0x00: return f"sll {REGS[rd]}, {REGS[rt]}, {sa}"
        if fn == 0x02: return f"srl {REGS[rd]}, {REGS[rt]}, {sa}"
        if fn == 0x03: return f"sra {REGS[rd]}, {REGS[rt]}, {sa}"
        if fn == 0x04: return f"sllv {REGS[rd]}, {REGS[rt]}, {REGS[rs]}"
        if fn == 0x06: return f"srlv {REGS[rd]}, {REGS[rt]}, {REGS[rs]}"
        if fn == 0x08: return f"jr {REGS[rs]}"
        if fn == 0x09: return f"jalr {REGS[rd]}, {REGS[rs]}"
        if fn == 0x20: return f"add {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x21: return f"addu {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x22: return f"sub {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x23: return f"subu {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x24: return f"and {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x25: return f"or {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x26: return f"xor {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x27: return f"nor {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x2A: return f"slt {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        if fn == 0x2B: return f"sltu {REGS[rd]}, {REGS[rs]}, {REGS[rt]}"
        return f"special_0x{fn:02X}"
    if op == 0x02: return f"j 0x{target:08X}"
    if op == 0x03: return f"jal 0x{target:08X}"
    if op == 0x04: return f"beq {REGS[rs]}, {REGS[rt]}, 0x{va + 4 + simm*4:08X}"
    if op == 0x05: return f"bne {REGS[rs]}, {REGS[rt]}, 0x{va + 4 + simm*4:08X}"
    if op == 0x06: return f"blez {REGS[rs]}, 0x{va + 4 + simm*4:08X}"
    if op == 0x07: return f"bgtz {REGS[rs]}, 0x{va + 4 + simm*4:08X}"
    if op == 0x08: return f"addi {REGS[rt]}, {REGS[rs]}, {simm}"
    if op == 0x09: return f"addiu {REGS[rt]}, {REGS[rs]}, {simm}"
    if op == 0x0A: return f"slti {REGS[rt]}, {REGS[rs]}, {simm}"
    if op == 0x0B: return f"sltiu {REGS[rt]}, {REGS[rs]}, {simm}"
    if op == 0x0C: return f"andi {REGS[rt]}, {REGS[rs]}, 0x{imm:04X}"
    if op == 0x0D: return f"ori {REGS[rt]}, {REGS[rs]}, 0x{imm:04X}"
    if op == 0x0E: return f"xori {REGS[rt]}, {REGS[rs]}, 0x{imm:04X}"
    if op == 0x0F: return f"lui {REGS[rt]}, 0x{imm:04X}"
    if op == 0x20: return f"lb {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x21: return f"lh {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x23: return f"lw {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x24: return f"lbu {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x25: return f"lhu {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x28: return f"sb {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x29: return f"sh {REGS[rt]}, {simm}({REGS[rs]})"
    if op == 0x2B: return f"sw {REGS[rt]}, {simm}({REGS[rs]})"
    return f"op_0x{op:02X}"

def disasm_range(elf_bytes, start_va, count):
    lines = []
    for i in range(count):
        va = start_va + i * 4
        off = va - 0x00100000 + 0x1000
        w = struct.unpack("<I", elf_bytes[off:off+4])[0]
        lines.append(f"0x{va:08X}: {disasm_mips(w, va):<35} (0x{w:08X})")
    return "\n".join(lines)

if __name__ == "__main__":
    with open("iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso", "rb") as f:
        f.seek(0x92000)
        elf = f.read(1528668)
        print(disasm_range(elf, 0x001B2B28, 126))

