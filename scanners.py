# -*- coding: utf-8 -*-
"""
TXR2 / Dreamcast multi-format scanner & PRS-aware extractor (v2)

Finds and carves:
- PVR family: PVRT / PVPL / GBIX + legacy headers (PVR!, PVR\x03, PVR\x04)
- CRI textures: GVR (raw lumps) and containers: GVM (GVMH)
- SEGA containers: PVM (PVMH)
- PS2 leftovers: TIM2 / TM2F  (for multi-platform builds)
- Recursively scans inside PRS-compressed blocks (‘PRS’) and inside PVM/GVM payloads.

Main entry:
    robust_scan_to_dir(in_bytes: bytes, out_dir: str, tag: str, origin: str) -> dict[counts]

Outputs:
    <out_dir>/<tag>_<origin>_<ext>_<offset>.{pvr,pvp,gbix,gvr,gvm,pvm,tm2,tm2f}
    <out_dir>/PRS_EXTRACT/... for decompressed payloads (each recursively scanned)

Notes:
- Does not attempt to *decode* GVR; it carves them so you can feed to external GvrTool.
- PVR decode is handled elsewhere by PyPVR (GUI uses it for preview/PNG export).
"""
from __future__ import annotations
import re, os
from pathlib import Path

# --------------------------- PRS decompressors ---------------------------
def _prs_decompress_basic(buf: bytes, start: int = 0):
    """Simple, widely-compatible CRI PRS decoder; returns (bytes, consumed) or (None, 0)."""
    if buf[start:start+3] != b'PRS':
        return None, 0
    i = start + 3
    out = bytearray()
    bit = 0; cmd = 0
    def getbit():
        nonlocal bit, cmd, i
        if bit == 0:
            if i >= len(buf): return 0
            cmd = buf[i]; i += 1; bit = 8
        b = cmd & 1; cmd >>= 1; bit -= 1; return b
    def getbyte():
        nonlocal i
        if i >= len(buf): return 0
        b = buf[i]; i += 1; return b
    while i < len(buf):
        if getbit():
            out.append(getbyte())
        else:
            if getbit():
                a = getbyte(); b = getbyte()
                off = ((b << 8) | a) >> 3
                amount = (a & 7)
                amount = (getbyte() + 1) if amount == 0 else (amount + 2)
                sp = len(out) - 0x2000 + off
            else:
                amount = (getbit() << 1) | getbit()
                off = getbyte()
                amount += 2
                sp = len(out) - 0x100 + off
            for _ in range(amount):
                if sp < 0: out.append(0)
                elif sp < len(out): out.append(out[sp])
                else: out.append(0)
                sp += 1
    return bytes(out), i - start

def _prs_decompress_nights(buf: bytes, start: int = 0):
    """Alternative bitstream variant used by some builds; returns (bytes, consumed) or (None, 0)."""
    if buf[start:start+3] != b'PRS':
        return None, 0
    i = start + 3
    out = bytearray()
    bitbuf = 0; bits = 0
    def getbit():
        nonlocal bitbuf, bits, i
        if bits == 0:
            if i >= len(buf): return 0
            bitbuf = buf[i]; i += 1; bits = 8
        b = bitbuf & 1; bitbuf >>= 1; bits -= 1; return b
    while True:
        if getbit():
            if i >= len(buf): break
            out.append(buf[i]); i += 1
        else:
            if getbit():
                if i+2 > len(buf): break
                a = buf[i]; b = buf[i+1]; i += 2
                offs = ((b & 0xF0) << 4) | a
                cnt  = (b & 0x0F) + 3
                if offs == 0: break
                src = len(out) - offs
                if src < 0: return None, 0
                for _ in range(cnt):
                    out.append(out[src]); src += 1
            else:
                if i+3 > len(buf): break
                a = buf[i]; b = buf[i+1]; c = buf[i+2]; i += 3
                cnt  = ((c & 0xE0) >> 5) + 2
                offs = ((c & 0x1F) << 8) | b
                src = len(out) - offs
                if src < 0: return None, 0
                for _ in range(cnt):
                    out.append(out[src]); src += 1
    return bytes(out), i - start

def _prs_try_all(buf: bytes, start: int):
    for fn in (_prs_decompress_basic, _prs_decompress_nights):
        dec, consumed = fn(buf, start)
        if dec and len(dec) > 0:
            return dec, consumed
    return None, 0

# --------------------------- helpers ---------------------------
def _next_tag(buf: bytes, start: int, tags: list[bytes]) -> int:
    cand = [buf.find(t, start) for t in tags]
    cand = [c for c in cand if c != -1]
    return min(cand) if cand else len(buf)

def _carve_range(buf: bytes, start: int, tags_next: list[bytes], hard_cap: int = 8*1024*1024):
    nxt = _next_tag(buf, start+4, tags_next)
    end = min(len(buf), max(start+16, nxt))  # at least some payload
    end = min(end, start + hard_cap)
    return start, end

def _dump(out_dir: Path, stem: str, ext: str, start: int, end: int, data: bytes):
    out = out_dir / f"{stem}_{start:08X}.{ext}"
    out.write_bytes(data[start:end])
    return out

# --------------------------- main scan ---------------------------
def robust_scan_to_dir(in_bytes: bytes, out_dir: str, tag: str, origin: str, _depth: int = 0):
    """
    Scan one blob, carve known chunks, optionally recurse into PRS/PVM/GVM.
    _depth avoids infinite recursion.
    """
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stem = f"{tag}_{origin}"
    counts = {"pvr":0,"pvp":0,"gbix":0,"gvr":0,"pvm":0,"gvm":0,"tm2":0,"tm2f":0,"prs":0}

    # ---- PVR family (PVRT/PVPL/GBIX + legacy PVR!, PVR\x03, PVR\x04) ----
    pvr_like = [(b"PVRT","pvr"), (b"PVPL","pvp")]
    legacy_pvr = [b"PVR!", b"PVR\x03", b"PVR\x04"]
    for sig, ext in pvr_like:
        i = 0
        while True:
            p = in_bytes.find(sig, i)
            if p == -1: break
            end = p + 8
            if end <= len(in_bytes):
                size = int.from_bytes(in_bytes[p+4:end], "little") + 8
                if 0x10 <= size <= len(in_bytes) - p:
                    _dump(out, stem, ext, p, p+size, in_bytes); counts[ext]+=1
                else:
                    s,e = _carve_range(in_bytes, p, [b"PVRT",b"PVPL",b"GBIX",b"GVR",b"PVMH",b"GVMH"])
                    _dump(out, stem, ext, s, e, in_bytes); counts[ext]+=1
            i = p + 4
    # GBIX metadata
    i = 0
    while True:
        p = in_bytes.find(b"GBIX", i)
        if p == -1: break
        if p+8 <= len(in_bytes):
            size = int.from_bytes(in_bytes[p+4:p+8], "little")
            end = min(len(in_bytes), p+8+max(0,size))
            _dump(out, stem, "gbix", p, end, in_bytes); counts["gbix"]+=1
        else:
            s,e = _carve_range(in_bytes, p, [b"PVRT",b"PVPL",b"GBIX",b"GVR"])
            _dump(out, stem, "gbix", s, e, in_bytes); counts["gbix"]+=1
        i = p + 4
    # Legacy PVR* headers (carve best-effort)
    for legacy in legacy_pvr:
        i = 0
        while True:
            p = in_bytes.find(legacy, i)
            if p == -1: break
            s,e = _carve_range(in_bytes, p, [b"PVRT",b"PVPL",b"GBIX",b"GVR",b"PVMH",b"GVMH",legacy])
            _dump(out, stem, "pvr", s, e, in_bytes); counts["pvr"]+=1
            i = p + 4

    # ---- TIM2 / TM2F ----
    for sig, ext in ((b"TIM2","tm2"), (b"TM2F","tm2f")):
        i = 0
        while True:
            p = in_bytes.find(sig, i)
            if p == -1: break
            s,e = _carve_range(in_bytes, p, [b"TIM2", b"TM2F", b"PVRT", b"GVR", b"PVMH", b"GVMH"])
            _dump(out, stem, ext, s, e, in_bytes); counts[ext]+=1
            i = p + 4

    # ---- PVM/GVM containers + direct GVR ----
    for sig, ext in ((b"PVMH","pvm"), (b"GVMH","gvm")):
        i = 0
        while True:
            p = in_bytes.find(sig, i)
            if p == -1: break
            s,e = _carve_range(in_bytes, p, [b"PVMH", b"GVMH", b"PVRT", b"GVR"])
            blob = _dump(out, stem, ext, s, e, in_bytes); counts[ext]+=1
            # Recurse into container payload to pick inner PVRT/GVR
            if _depth < 2:
                sub = robust_scan_to_dir(in_bytes[s:e], str(out / f"{blob.stem}_EXT"), tag=f"{tag}", origin=f"{origin}_{ext}", _depth=_depth+1)
                for k,v in sub.items(): counts[k] = counts.get(k,0)+v
            i = p + 4

    # Direct GVR/GVRT (CRI texture lumps, sometimes preceded by GBIX)
    for mark in (b"GVR", b"GVRT"):
        i = 0
        while True:
            p = in_bytes.find(mark, i)
            if p == -1: break
            # try to include preceding GBIX if within 64 bytes
            gb = in_bytes.rfind(b"GBIX", max(0,p-64), p)
            start = gb if gb != -1 else p
            s,e = _carve_range(in_bytes, start, [b"GVR", b"GVRT", b"GBIX", b"PVRT", b"PVMH", b"GVMH"])
            _dump(out, stem, "gvr", s, e, in_bytes); counts["gvr"]+=1
            i = p + 3

    # ---- PRS blocks → decompress and recurse ----
    prs_dir = out / "PRS_EXTRACT"
    i = 0; idx = 0
    while True:
        p = in_bytes.find(b"PRS", i)
        if p == -1: break
        dec, consumed = _prs_try_all(in_bytes, p)
        if dec and len(dec) > 0:
            prs_dir.mkdir(parents=True, exist_ok=True)
            blob_path = prs_dir / f"{stem}_prs_{idx:03d}.bin"
            blob_path.write_bytes(dec)
            counts["prs"] += 1; idx += 1
            # recurse into decompressed payload
            if _depth < 3:
                sub = robust_scan_to_dir(dec, str(prs_dir / f"{blob_path.stem}_EXT"), tag=f"{tag}_prs{idx-1}", origin=origin, _depth=_depth+1)
                for k,v in sub.items(): counts[k] = counts.get(k,0)+v
            i = p + max(consumed, 3)
        else:
            i = p + 3

    return counts
