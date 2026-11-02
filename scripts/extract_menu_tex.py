import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
import struct
from iso_tool import IsoHandler
from afs_tool import AfsArchive
from pac_tool import PacArchive
from lzr_tool import decompress_lzr
import tex_tool

out_dir = Path('extracted_menu_textures')
out_dir.mkdir(exist_ok=True)

iso = IsoHandler('iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso')
rv_entry = [e for k, e in iso.entries.items() if 'RVCAPU2.AFS' in k][0]
with open('iso/Rosario to Vampire Capu 2 - Koi to Yume no Rhapsodia (Japan).iso', 'rb') as f:
    rv_afs = AfsArchive(f, base_offset=rv_entry.offset)
    afs1_entry = [e for e in rv_afs.entries if '1.afs' in e.name.lower()][0]
    afs1_offset = rv_entry.offset + afs1_entry.offset
    afs1 = AfsArchive(f, base_offset=afs1_offset)
    
    inspect_pacs = ['pac801000.pac', 'pac802000.pac', 'pac803000.pac', 'pac900000.pac', 'pac910000.pac']
    for p_name in inspect_pacs:
        matching = [e for e in afs1.entries if p_name in e.name.lower()]
        if not matching:
            continue
        e = matching[0]
        f.seek(afs1_offset + e.offset)
        pac = PacArchive(f.read(e.size))
        p_stem = Path(p_name).stem
        for pe in pac.entries:
            if pe.name.lower().endswith('.tex'):
                raw = decompress_lzr(pe.data) if pe.is_compressed else pe.data
                try:
                    fmt, w, h, pal_cnt, pix_sz, rsvd = struct.unpack('<HHHHII', raw[:16])
                    raw_pal = raw[16 + pix_sz : 16 + pix_sz + pal_cnt * 4].ljust(1024, b'\x00')
                    pal = tex_tool.swizzle_palette(raw_pal)
                    pixel_data = raw[16 : 16 + pix_sz]
                    rgba = bytearray(w * h * 4)
                    for i, idx in enumerate(pixel_data):
                        r, g, b, a_ps2 = pal[idx * 4 : (idx + 1) * 4]
                        a_scaled = min(255, a_ps2 * 2) if a_ps2 <= 128 else 255
                        rgba[i * 4 : (i + 1) * 4] = [r, g, b, a_scaled]
                    png_bytes = tex_tool.encode_png(w, h, rgba)
                    stem_tex = pe.name.lower().replace('.tex', '')
                    out_path = out_dir / f"{p_stem}_{stem_tex}.png"
                    out_path.write_bytes(png_bytes)
                    print(f"Saved {out_path.name} ({w}x{h})")
                except Exception as ex:
                    print(f"Failed {pe.name}: {ex}")
