
#!/usr/bin/env python3
from pathlib import Path
from math import ceil
from PIL import Image
import numpy as np
import sys

def part1by1(n):
    n &= 0xFFFF
    n = (n | (n << 8)) & 0x00FF00FF
    n = (n | (n << 4)) & 0x0F0F0F0F
    n = (n | (n << 2)) & 0x33333333
    n = (n | (n << 1)) & 0x55555555
    return n

def morton_yx(x,y): return part1by1(y) | (part1by1(x) << 1)

def pal_1555(hdr):
    pals=[]
    for i in range(0,32,2):
        c=int.from_bytes(hdr[i:i+2],'little')
        a=255 if ((c>>15)&1) else 0
        r=((c>>10)&0x1F)*255//31
        g=((c>>5)&0x1F)*255//31
        b=(c&0x1F)*255//31
        pals.append((r,g,b,a))
    return pals

def pal_565(hdr):
    pals=[]
    for i in range(0,32,2):
        c=int.from_bytes(hdr[i:i+2],'little')
        r=((c>>11)&0x1F)*255//31
        g=((c>>5)&0x3F)*255//63
        b=(c&0x1F)*255//31
        pals.append((r,g,b,255))
    return pals

def pal_4444(hdr):
    pals=[]
    for i in range(0,32,2):
        c=int.from_bytes(hdr[i:i+2],'little')
        a=((c>>12)&0xF)*17
        r=((c>>8)&0xF)*17
        g=((c>>4)&0xF)*17
        b=(c&0xF)*17
        pals.append((r,g,b,a))
    return pals

def pal_5551(hdr):
    pals=[]
    for i in range(0,32,2):
        c=int.from_bytes(hdr[i:i+2],'little')
        a=255 if (c & 1) else 0
        r=((c>>11)&0x1F)*255//31
        g=((c>>6) &0x1F)*255//31
        b=((c>>1) &0x1F)*255//31
        pals.append((r,g,b,a))
    return pals

PAL_MAP = {"1555": pal_1555, "565": pal_565, "4444": pal_4444, "5551": pal_5551}

def decode_one(raw, palmode="4444", rule="even_high"):
    hdr=raw[:32]; payload=raw[32:]
    if len(payload)!=2048: return None
    pal = PAL_MAP[palmode](hdr)
    img=np.zeros((64,64,4), dtype=np.uint8)
    for y in range(64):
        for x in range(64):
            m = morton_yx(x,y)            # Y-first twiddle
            b = payload[m>>1]
            # nibble rule: high-nibble for even m, low for odd  (PAL4 high-first)
            if rule=="even_high":
                idx = (b>>4)&0xF if (m & 1)==0 else (b & 0xF)
            else:
                idx = (b & 0xF) if (m & 1)==0 else ((b>>4)&0xF)
            img[y,x] = pal[idx]
    return Image.fromarray(img, 'RGBA')

def score_smooth(im):
    g = np.array(im.convert("L"), dtype=np.float32)
    gx = np.abs(g[:,1:] - g[:,:-1]).mean()
    gy = np.abs(g[1:,:] - g[:-1,:]).mean()
    return gx+gy

def parse_afs(path: Path):
    with open(path, "rb") as f:
        head = f.read(4)
        if head[:3] != b"AFS": raise SystemExit("Not an AFS")
        n = int.from_bytes(f.read(4),"little")
        entries = []
        for _ in range(n):
            off = int.from_bytes(f.read(4),"little")
            size= int.from_bytes(f.read(4),"little")
            entries.append((off,size))
        return entries

def main():
    if len(sys.argv)<2:
        print("Usage: python decode_sticker_afs_v3.py STICKER.AFS [--all]")
        return 2
    afs = Path(sys.argv[1])
    dump_all = ("--all" in sys.argv)
    out = afs.parent/"_STICKER_DEC_v3"
    out.mkdir(parents=True, exist_ok=True)
    entries = parse_afs(afs)
    with open(afs,"rb") as f:
        for i,(off,size) in enumerate(entries):
            f.seek(off); raw = f.read(size)
            if size != 2080: continue
            # try 8 combos and pick the smoothest (removes checkerboard artifacts)
            best = None
            best_im = None
            for palmode in ("4444","1555","565","5551"):
                for rule in ("even_high","even_low"):
                    im = decode_one(raw, palmode, rule)
                    s  = score_smooth(im)
                    if dump_all:
                        im.save(out / f"{i:04d}_{palmode}_{rule}.png")
                    if best is None or s < best[0]:
                        best = (s, palmode, rule)
                        best_im = im
            best_im.save(out / f"{i:04d}.png")
    # tilesheet
    files = sorted(out.glob("[0-9][0-9][0-9][0-9].png"))
    if files:
        W,H = Image.open(files[0]).size
        cols = 10; rows = (len(files)+cols-1)//cols
        sheet = Image.new("RGBA",(W*cols,H*rows))
        for idx, p in enumerate(files):
            im = Image.open(p)
            r,c = divmod(idx, cols)
            sheet.paste(im,(c*W,r*H))
        sheet.save(out/"tilesheet.png")
    print("Output:", out)

if __name__=="__main__":
    raise SystemExit(main())
