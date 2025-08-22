#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TXR2 Texture Toolkit — ALL-IN-ONE (AFS + embedded PyPVR + Preview + Recipes)
Language: RU/EN switchable at runtime. Uses embedded PyPVR (no external CLI).
"""

import os, sys
import pathlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from scanners import robust_scan_to_dir


# ---- Tiny tooltip helper ----
class _Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, _=None):
        if self.tip or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget); self.tip.wm_overrideredirect(True)
        lbl = ttk.Label(self.tip, text=self.text, relief="solid", borderwidth=1, background="#ffffe0")
        lbl.pack(ipadx=6, ipady=3)
        self.tip.wm_geometry(f"+{x}+{y}")
    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip = None


# ---- embed PyPVR ----
try:
    import pypvr
except ImportError:
    from pypvr_embedded import pypvr

# ---- Tiny tooltip helper ----
class _Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, _=None):
        if self.tip or not self.text: return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget); self.tip.wm_overrideredirect(True)
        lbl = ttk.Label(self.tip, text=self.text, relief="solid", borderwidth=1, background="#ffffe0")
        lbl.pack(ipadx=6, ipady=3)
        self.tip.wm_geometry(f"+{x}+{y}")
    def hide(self, _=None):
        if self.tip: self.tip.destroy(); self.tip = None


##SPLIT##
try:
    import pypvr
except ImportError:
    from pypvr_embedded import pypvr
sys.modules["pypvr"] = pypvr



# ---- Updated CRI PRS decompressor ----
# The previous minimal decompressor did not work for some Dreamcast PRS blocks.
# This implementation is adapted from the NiGHTS LZS decompressor and works
# with PRS streams found in many SEGA games.  It returns both the
# decompressed bytes and the number of input bytes consumed.
def _prs_decompress(buf, start=0):
    """Decompress a PRS block beginning at `start` in `buf`.  If the
    signature 'PRS' is not present, returns (None, 0).  The algorithm
    operates on a sliding window and is based on LZ77; see:【146627541408994†L92-L131】 for a reference.
    """
    if buf[start:start+3] != b'PRS':
        return None, 0
    i = start + 3
    out = bytearray()
    bit = 0
    cmd = 0
    # helper to read a single bit
    def getbit():
        nonlocal bit, cmd, i
        if bit == 0:
            if i >= len(buf):
                return 0
            cmd = buf[i]
            i += 1
            bit = 8
        res = cmd & 1
        cmd >>= 1
        bit -= 1
        return res
    # helper to read a byte
    def getByte():
        nonlocal i
        if i >= len(buf):
            return 0
        b = buf[i]
        i += 1
        return b
    while i < len(buf):
        if getbit():
            # literal byte
            out.append(getByte())
        else:
            if getbit():
                # short backref (0x2000 window)
                a = getByte()
                b = getByte()
                # compute offset and amount
                offset = ((b << 8) | a) >> 3
                amount = a & 7
                if amount == 0:
                    amount = getByte() + 1
                else:
                    amount += 2
                start_pos = len(out) - 0x2000 + offset
            else:
                # long backref (0x100 window)
                amount = 0
                amount = (amount << 1) | getbit()
                amount = (amount << 1) | getbit()
                offset = getByte()
                amount += 2
                start_pos = len(out) - 0x100 + offset
            # copy from out buffer
            for _ in range(amount):
                if start_pos < 0:
                    out.append(0)
                elif start_pos < len(out):
                    out.append(out[start_pos])
                else:
                    out.append(0)
                start_pos += 1
    consumed = i - start
    return bytes(out), consumed

def prs_extract_all_to_folder(container_bytes: bytes, out_dir: str, entry_label: str = "blob"):
    """Scan `container_bytes` for PRS signatures and decompress them into
    individual files under `out_dir`.  Returns the number of blocks
    decompressed.  If multiple PRS headers appear close together, each
    will be attempted; overlapping segments are skipped based on the
    consumed length reported by the decompressor.
    """
    import re, os
    os.makedirs(out_dir, exist_ok=True)
    found = 0
    last_end = -1
    for m in re.finditer(b"PRS", container_bytes):
        off = m.start()
        # skip if inside the previous decompressed segment
        if off < last_end:
            continue
        dec, consumed = _prs_decompress(container_bytes, start=off)
        if dec:
            with open(os.path.join(out_dir, f"{entry_label}_{found:03d}.bin"), "wb") as w:
                w.write(dec)
            found += 1
            # update last_end to skip overlapping signatures
            last_end = off + consumed
    return found

# ---- Pillow optional for preview ----
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

# ---- i18n ----
I18N = {
    "ru": {
        "lang_name": "Русский",
        "app_title": "TXR2 Texture Toolkit — Всё‑в‑одном",
        "tab_afs": "AFS / Контейнер",
        "tab_pvr": "PVR ⇄ PNG",
        "tab_repack": "Репак AFS",
        "tab_recipes": "Рецепты",
        "language": "Язык:",
        "container_label": "Контейнер (AFS/DAT/BIN/PVM/TEX):",
        "browse": "Обзор…",
        "scan_entries": "Сканировать записи",
        "extract_raw": "Извлечь RAW",
        "find_pvrt": "Найти PVRT/палитры",
        "preview": "Предпросмотр",
        "decode_selected_preview": "Декодировать выделенное → предпросмотр",
        "output_dir": "Папка вывода:",
        "loaded": "Загружен: {path}",
        "entries_n": "Записей: {n}",
        "extracted_n": "Извлечено {n} записей → {out}",
        "scan_complete": "Сканирование завершено. См. *_EXT и pvr_log.txt",
        "no_file": "Не выбран файл",
        "pick_container": "Выберите контейнер",
        "no_pillow": "Нет Pillow — установите пакет 'Pillow' для предпросмотра.",
        "no_afs": "Сначала просканируйте AFS.",
        "preview_entry": "Предпросмотр записи #{idx}",
        "select_output": "Выберите папку вывода",
        "source_label": "Источник (файл или папка):",
        "output_label": "Папка вывода:",
        "decode_pvr": "Декодировать PVR→PNG",
        "encode_pvr": "Кодировать PNG→PVR",
        "list_files": "Показать файлы",
        "options_title": "Параметры кодирования",
        "color": "Цвет",
        "texture": "Текстура",
        "mm": "Mipmaps (-mm)",
        "flip": "Отразить (-flip)",
        "gbix": "GBIX (-gi)",
        "encode": "Кодировать",
        "cancel": "Отмена",
        "decode_complete": "Декодирование завершено",
        "encode_complete": "Кодирование завершено",
        "source_needed": "Выберите источник",
        "src_pvr_needed": "Укажите PVR/папку",
        "src_png_needed": "Укажите PNG/папку",
        "src_afs_needed": "Выберите исходный AFS",
        "load_entries": "Загрузить записи",
        "set_replacement": "Задать замену…",
        "clear_replacement": "Очистить замену",
        "output_afs": "Выходной AFS:",
        "choose": "Выбрать…",
        "write_new_afs": "Записать новый AFS (safe replace)",
        "no_replacements": "Нет замен — укажите хотя бы одну запись.",
        "done": "Готово",
        "repack_saved": "Патченный AFS сохранён:\n{dst}",
        "repack_failed": "Сбой репака",
        "recipes_r1": "Рецепт 1 — Сканировать контейнер → PVRT/PVPL → PNG + pvr_log.txt",
        "recipes_r1_run": "Выполнить",
        "recipes_r2": "Рецепт 2 — Реимпорт по pvr_log.txt (код PNG→PVR и запись в контейнер)",
        "recipes_r2_run": "Реимпорт",
        "recipes_r3": "Рецепт 3 — Пакетный re-encode по pvr_log (только PVR)",
        "recipes_r3_run": "Кодировать",
        "pick_log": "Укажите pvr_log.txt",
        "encode_only": "PVR перекодированы по логу. Контейнер не изменён.",
        "reimport_done": "Реимпорт завершён. Проверьте резервные копии контейнера!",
        "no_pvrt_found": "Ничего не найдено. Возможно, контейнер PRS‑сжат; распакуйте его перед сканированием.",
        # Help/instruction texts
        "afs_help": "Шаги: 1) Выберите файл‑контейнер (.afs/.bin/.dat). 2) Нажмите «Сканировать записи», чтобы увидеть список. 3) Для извлечения RAW выберите папку вывода и нажмите «Извлечь RAW». 4) Чтобы найти текстуры PVRT и палитры, выберите папку вывода и нажмите «Найти PVRT/палитры». 5) Выберите запись и нажмите «Декодировать выделенное → предпросмотр» для просмотра. Примечание: если ничего не найдено, контейнер может быть PRS‑сжат; распакуйте его внешним инструментом.",
        "pvr_help": "Эта вкладка конвертирует между текстурами PVR/PVP и изображениями PNG. Выберите PVR или папку и нажмите «Декодировать PVR→PNG», чтобы получить PNG. Выберите PNG или папку, настройте параметры (формат пикселей, текстуры, мипмапы) и нажмите «Кодировать PNG→PVR», чтобы создать PVR и PVP. «Показать файлы» выводит список файлов источника.",
        "repack_help": "Создание патченного AFS. 1) Выберите исходный AFS и нажмите «Загрузить записи». 2) Для каждой записи, которую нужно заменить, укажите новый файл (размер не должен превышать исходный). 3) Выберите путь для сохранения патченного AFS. 4) Нажмите «Записать новый AFS». Только выбранные записи заменяются; остальные копируются без изменений.",
        "recipes_help": "«Рецепты» автоматизируют типовые операции:\n• Рецепт 1 сканирует контейнер, извлекает PVR/PVP текстуры в PNG и создаёт файл pvr_log.txt с описанием каждой конверсии.\n• Рецепт 2 берёт pvr_log.txt, перекодирует изменённые PNG обратно в PVR и записывает их в контейнер по исходным смещениям. Используйте для реимпорта правок.\n• Рецепт 3 читает pvr_log.txt и перекодирует все PNG из списка в PVR‑файлы в выбранную папку, не изменяя контейнер.",
        "btn_full_deprs": "Полный dePRS → поиск PVRT",
        "tip_full_deprs": "Распаковать все PRS (рекурсивно) и сразу найти/вытащить PVRT/PVPL. Результаты: *_DEPRS и *_DEPRS_PVR, PNG идёт в папку вывода.",
    },
    "en": {
        "lang_name": "English",
        "app_title": "TXR2 Texture Toolkit — All‑in‑One",
        "tab_afs": "AFS / Container",
        "tab_pvr": "PVR ⇄ PNG",
        "tab_repack": "Repack AFS",
        "tab_recipes": "Recipes",
        "language": "Language:",
        "container_label": "Container (AFS/DAT/BIN/PVM/TEX):",
        "browse": "Browse…",
        "scan_entries": "Scan entries",
        "extract_raw": "Extract RAW",
        "find_pvrt": "Find PVRT & palettes",
        "preview": "Preview",
        "decode_selected_preview": "Decode selected → preview",
        "output_dir": "Output directory:",
        "loaded": "Loaded: {path}",
        "entries_n": "Entries: {n}",
        "extracted_n": "Extracted {n} entries → {out}",
        "scan_complete": "Scan complete. See *_EXT and pvr_log.txt",
        "no_file": "No file selected",
        "pick_container": "Pick a container",
        "no_pillow": "Pillow not installed. Install 'Pillow' for preview.",
        "no_afs": "Scan AFS first.",
        "preview_entry": "Preview entry #{idx}",
        "select_output": "Choose output directory",
        "source_label": "Source (file or folder):",
        "output_label": "Output directory:",
        "decode_pvr": "Decode PVR→PNG",
        "encode_pvr": "Encode PNG→PVR",
        "list_files": "List files",
        "options_title": "Encoding options",
        "color": "Color",
        "texture": "Texture",
        "mm": "Mipmaps (-mm)",
        "flip": "Flip (-flip)",
        "gbix": "GBIX (-gi)",
        "encode": "Encode",
        "cancel": "Cancel",
        "decode_complete": "Decode complete",
        "encode_complete": "Encode complete",
        "source_needed": "Select a source",
        "src_pvr_needed": "Pick a PVR/folder",
        "src_png_needed": "Pick a PNG/folder",
        "src_afs_needed": "Pick a source AFS",
        "load_entries": "Load entries",
        "set_replacement": "Set replacement…",
        "clear_replacement": "Clear replacement",
        "output_afs": "Output AFS:",
        "choose": "Choose…",
        "write_new_afs": "Write new AFS (safe replace)",
        "no_replacements": "No replacements — set at least one entry.",
        "done": "Done",
        "repack_saved": "Patched AFS saved:\n{dst}",
        "repack_failed": "Repack failed",
        "recipes_r1": "Recipe 1 — Scan container → PVRT/PVPL → PNG + pvr_log.txt",
        "recipes_r1_run": "Run",
        "recipes_r2": "Recipe 2 — Reimport from pvr_log.txt (encode PNG→PVR & write back to container)",
        "recipes_r2_run": "Reimport",
        "recipes_r3": "Recipe 3 — Batch re-encode per pvr_log (PVR only)",
        "recipes_r3_run": "Encode",
        "pick_log": "Pick pvr_log.txt",
        "encode_only": "PVRs encoded per log. Container not modified.",
        "reimport_done": "Reimport complete. Check your container backups!",
        "no_pvrt_found": "Nothing found. The container may be PRS‑compressed; decompress it before scanning.",
        # Help/instruction texts
        "afs_help": "Steps: 1) Select a container file (.afs/.bin/.dat). 2) Click ‘Scan entries’ to display the list of entries. 3) To extract RAW entries, choose an output folder then press ‘Extract RAW’. 4) To search for PVRT textures and palettes, choose an output folder then press ‘Find PVRT & palettes’. 5) Select an entry and click ‘Decode selected → preview’ to preview textures. Note: if nothing is found the container may be PRS‑compressed and must be decompressed externally first.",
        "pvr_help": "This tab converts between PVR/PVP textures and PNG images. Choose a PVR file or folder and click ‘Decode PVR→PNG’ to get PNG. Choose a PNG file or folder, set options (pixel format, texture type, mipmaps) and click ‘Encode PNG→PVR’ to create PVR and PVP files. ‘List files’ prints the source file list.",
        "repack_help": "Creating a patched AFS. 1) Select the original AFS and click ‘Load entries’. 2) For each entry you want to replace, specify a new file (its size must not exceed the original). 3) Choose where to save the patched AFS. 4) Click ‘Write new AFS’. Only selected entries are replaced; all others are copied unchanged.",
        "recipes_help": "The ‘Recipes’ automate common tasks:\n• Recipe 1 scans a container, extracts PVR/PVP textures to PNG and creates a pvr_log.txt describing each conversion.\n• Recipe 2 reads a pvr_log.txt, re‑encodes modified PNGs back to PVR and writes them into the container at the original offsets. Use this to reimport your edits.\n• Recipe 3 reads a pvr_log.txt and re‑encodes all listed PNGs into PVR files in a chosen folder, without modifying any container.",
    }
}
# --- Sticker decoder i18n additions ---
try:
    I18N['ru'].update({
        "decode_sticker_auto": "Отдельные текстуры → PNG",
        "decoding_stickers": "Декод текстур…",
        "decoded_stickers_n": "Готово: {n} текстур → {out}",
    })
    I18N['en'].update({
        "decode_sticker_auto": "Separate textures → PNG",
        "decoding_stickers": "Decoding textures…",
        "decoded_stickers_n": "Done: {n} textures → {out}",
    })
except Exception:
    pass



# ---- AFS minimal reader ----
class AFSArchive:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.entries = []
        self._read()
    def _read(self):
        with open(self.path, "rb") as f:
            if f.read(4) != b"AFS\x00":
                raise ValueError("Not an AFS archive (missing 'AFS\\0')")
            n = int.from_bytes(f.read(4), "little")
            f.read(4)  # unknown/align
            table = [tuple(int.from_bytes(f.read(4), "little") for _ in range(2)) for _ in range(n)]
            f.seek(0,2); total=f.tell()
            def plaus_so(pair): size,off=pair; return 0<off<total and 0<size<=total-off
            use_so = sum(1 for p in table if plaus_so(p)) >= n//2
            self.entries = [{"index":i,"offset":(b if use_so else a),"size":(a if use_so else b)} for i,(a,b) in enumerate(table)]
    def read_entry_bytes(self, idx):
        e = self.entries[idx]
        with open(self.path,"rb") as f:
            f.seek(e["offset"]); return f.read(e["size"])
    def extract_all(self, out_dir):
        out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
        with open(self.path,"rb") as f:
            for e in self.entries:
                if e["offset"] and e["size"]:
                    f.seek(e["offset"]); (out/f"entry_{e['index']:04d}.bin").write_bytes(f.read(e["size"]))
        return len(self.entries)
    def replace_in_place(self, repl:dict, out_path:Path):
        data = bytearray(Path(self.path).read_bytes())
        for idx,newp in repl.items():
            idx=int(idx); e=self.entries[idx]; off, size = e["offset"], e["size"]
            chunk = pathlib.Path(newp).read_bytes()
            if len(chunk)>size: raise ValueError(f"Entry #{idx} replacement is larger than original ({len(chunk)}>{size}).")
            data[off:off+len(chunk)] = chunk
            if len(chunk)<size: data[off+len(chunk):off+size] = b"\x00"*(size-len(chunk))
        outp = pathlib.Path(out_path); outp.write_bytes(bytes(data)); return outp

# ---- GUI ----
# ---- Full PRS recursive decompressor + PVRT splitter ----
import re as _re_deprs, struct as _st_deprs, pathlib as _pl_deprs

def _read_u32le_deprs(b, off):
    return int.from_bytes(b[off:off+4], 'little')

def _prs_decompress_nights(data: bytes, start: int = 0):
    """CRI PRS (NiGHTS-like) bitstream decoder. Returns (out_bytes, consumed) or (None, None)."""
    i = start
    if data[i:i+3] != b'PRS':
        return (None, None)
    i += 3
    out = bytearray()
    bitbuf = 0
    bits = 0
    def getbit():
        nonlocal bitbuf, bits, i
        if bits == 0:
            if i >= len(data): return 0
            bitbuf = data[i]; i += 1; bits = 8
        b = bitbuf & 1
        bitbuf >>= 1; bits -= 1
        return b
    try:
        while True:
            if getbit() == 1:
                if i >= len(data): break
                out.append(data[i]); i += 1
            else:
                if getbit() == 1:
                    if i+2 > len(data): break
                    a = data[i]; b = data[i+1]; i += 2
                    offs = ((b & 0xF0) << 4) | a
                    cnt  = (b & 0x0F) + 3
                    if offs == 0:  # end
                        break
                    src = len(out) - offs
                    if src < 0: return (None, None)
                    for _ in range(cnt):
                        out.append(out[src]); src += 1
                else:
                    if i+3 > len(data): break
                    a = data[i]; b = data[i+1]; c = data[i+2]; i += 3
                    cnt  = (a | ((b & 0xE0) << 3)) + 2
                    offs = ((b & 0x1F) << 8) | c
                    src = len(out) - offs
                    if src < 0: return (None, None)
                    for _ in range(cnt):
                        out.append(out[src]); src += 1
    except Exception:
        return (None, None)
    return (bytes(out), i - start)

def _prs_decompress_auto(data: bytes, start: int):
    """Try plain NiGHTS bit order; if fails, try per-byte bit-reversed stream."""
    o1,c1 = _prs_decompress_nights(data, start)
    if o1 and c1: return (o1,c1)
    if data[start:start+3] != b'PRS': return (None, None)
    tbl = bytes(int(f'{i:08b}'[::-1],2) for i in range(256))
    head = data[start:start+3]
    rest = bytes(tbl[b] for b in data[start+3:])
    alt  = head + rest
    o2,c2 = _prs_decompress_nights(alt, 0)
    if o2 and c2: return (o2,c2)
    return (None, None)

def _split_pvrt_pvpl(buf: bytes, out_dir: _pl_deprs.Path, base_name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for m in _re_deprs.finditer(b'PVRT', buf):
        pos = m.start()
        if pos+8 <= len(buf):
            size = _read_u32le_deprs(buf, pos+4) + 8
            if 0 < size <= len(buf)-pos:
                (out_dir / f'{base_name}_pvrt_{pos:08X}.pvr').write_bytes(buf[pos:pos+size])
                count += 1
    for m in _re_deprs.finditer(b'PVPL', buf):
        pos = m.start()
        if pos+8 <= len(buf):
            size = _read_u32le_deprs(buf, pos+4) + 8
            if 0 < size <= len(buf)-pos:
                (out_dir / f'{base_name}_pvpl_{pos:08X}.pvp').write_bytes(buf[pos:pos+size])
                count += 1
    return count




def full_deprs_and_scan(input_path: str, out_dir: str, max_depth: int = 6):
    """Recursive PRS unpack + PVRT/PVPL scan (base + leaves) using robust_scan_to_dir."""
    import re
    from pathlib import Path as _P
    p_in=_P(input_path); p_out=_P(out_dir); p_out.mkdir(parents=True, exist_ok=True)
    base=p_in.stem; data=p_in.read_bytes()
    deprs=p_out/f"{base}_DEPRS"; pvrdir=p_out/f"{base}_DEPRS_PVR"
    deprs.mkdir(exist_ok=True); pvrdir.mkdir(exist_ok=True)

    # 1) base scan
    c_base = robust_scan_to_dir(data, str(pvrdir), base, "base")

    # 2) recurse PRS blocks
    leaves=[]
    def _prs(buf,pos):
        try:
            out,used=_prs_decompress_auto(buf,pos)
            if out and used: return out,used
        except Exception: pass
        return None,None

    def rec(buf, tag, d):
        found=False
        for m in re.finditer(b"PRS", buf):
            found=True
            pos=m.start(); out,used=_prs(buf,pos)
            if out:
                name=f"{tag}_d{d}_@{pos:08X}"; (deprs/f"{name}.bin").write_bytes(out)
                if d<max_depth and b"PRS" in out: rec(out, name, d+1)
                else: leaves.append((name,out))
        if not found: leaves.append((f"{tag}_raw", buf))

    rec(data, base, 0)

    c_leaf={"pvr":0,"pvp":0}
    for name,buf in leaves:
        r=robust_scan_to_dir(buf, str(pvrdir), name, "leaf")
        c_leaf["pvr"]+=r["pvr"]; c_leaf["pvp"]+=r["pvp"]

    total = c_base["pvr"]+c_base["pvp"]+c_leaf["pvr"]+c_leaf["pvp"]
    if total>0:
        try: pypvr.Pypvr.Decode(args_str=f'-scandir \"{pvrdir}\" -o \"{p_out}\" -fmt png -nolog')
        except Exception: pass

    return {"prs_blocks": len(list(re.finditer(b"PRS", data))),
            "base_pvr": c_base["pvr"], "base_pvp": c_base["pvp"],
            "leaf_pvr": c_leaf["pvr"], "leaf_pvp": c_leaf["pvp"],
            "total_pvrpvp": total, "deprs_dir": str(deprs), "pvr_dir": str(pvrdir)}
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang="ru"
        self.title(self.tr("app_title"))
        self.geometry("1200x740"); self.minsize(1000,620)
        self.afs_path=tk.StringVar(); self.out_dir=tk.StringVar(value=str(Path.cwd()/ "extracted"))
        self.status=tk.StringVar(value="Ready."); self.replacements={}; self._current_afs=None
        self._file_imgtk=None; self.preview_imgtk=None
        self.build_shell(); self.build_tabs()

    # i18n
    def tr(self,key,**kw):
        txt = I18N.get(self.lang, I18N["en"]).get(key, key); return txt.format(**kw) if kw else txt
    def set_language(self, code):
        self.lang = code
        self.title(self.tr("app_title"))
        # Safely rebuild notebook
        try:
            old = self.nb
            self.nb = ttk.Notebook(self)
            old.destroy()
        except Exception:
            self.nb = ttk.Notebook(self)
        # Remove status and rebuild tabs fresh
        for w in self.nb.winfo_children(): 
            try: w.destroy()
            except Exception: pass
        self.nb.pack_forget()
        self.nb.pack(fill=tk.BOTH, expand=True)
        self.build_tabs()

    # shell
    def build_shell(self):
        top=ttk.Frame(self); top.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(top, text=self.tr("language")).pack(side=tk.LEFT)
        box = ttk.Combobox(top, state="readonly", width=12, values=[I18N["ru"]["lang_name"], I18N["en"]["lang_name"]]); box.set(I18N[self.lang]["lang_name"])
        def on_change(_): self.set_language("ru" if box.get()==I18N["ru"]["lang_name"] else "en")
        box.bind("<<ComboboxSelected>>", on_change); box.pack(side=tk.LEFT, padx=6)
        self.nb=ttk.Notebook(self); self.nb.pack(fill=tk.BOTH, expand=True)
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill=tk.X, side=tk.BOTTOM)

    def build_tabs(self):
        self.tab_afs=ttk.Frame(self.nb); self.tab_pvr=ttk.Frame(self.nb); self.tab_repack=ttk.Frame(self.nb); self.tab_recipes=ttk.Frame(self.nb)
        self.nb.add(self.tab_afs, text=self.tr("tab_afs"))
        self.nb.add(self.tab_pvr, text=self.tr("tab_pvr"))
        self.nb.add(self.tab_repack, text=self.tr("tab_repack"))
        self.nb.add(self.tab_recipes, text=self.tr("tab_recipes"))
        self.build_tab_afs(); self.build_tab_pvr(); self.build_tab_repack(); self.build_tab_recipes()

    # AFS tab
    def build_tab_afs(self):
        frm=self.tab_afs
        # instruction label
        ttk.Label(frm, text=self.tr("afs_help"), wraplength=650, justify=tk.LEFT, foreground="grey").pack(fill=tk.X, padx=8, pady=(4,2))
        top=ttk.Frame(frm); top.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(top, text=self.tr("container_label")).pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.afs_path, width=68).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text=self.tr("browse"), command=self.on_browse_afs).pack(side=tk.LEFT)
        ttk.Button(top, text=self.tr("scan_entries"), command=self.on_scan_entries).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text=self.tr("extract_raw"), command=self.on_extract_raw).pack(side=tk.LEFT)
        ttk.Button(top, text=self.tr("find_pvrt"), command=self.on_scan_pvrt).pack(side=tk.LEFT, padx=6)

        top2 = ttk.Frame(frm); top2.pack(fill=tk.X, padx=8, pady=(0,6))
        self._btn_full_deprs = ttk.Button(top2, text=self.tr("btn_full_deprs"), command=self.on_full_deprs)
        self._btn_full_deprs.pack(side=tk.LEFT, padx=6)
        self._btn_sticker = ttk.Button(top2, text=self.tr("decode_sticker_auto"), command=self.on_decode_sticker_auto)
        self._btn_sticker.pack(side=tk.LEFT)
        try:
            _Tooltip(self._btn_full_deprs, self.tr("tip_full_deprs"))
        except Exception:
            pass
        mid=ttk.Panedwindow(frm, orient=tk.HORIZONTAL); mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        left=ttk.Frame(mid); right=ttk.Frame(mid); mid.add(left,weight=2); mid.add(right,weight=3)
        self.lst=tk.Listbox(left, selectmode=tk.SINGLE); self.lst.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.lst.bind("<<ListboxSelect>>", self.on_entry_select)
        sc=ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.lst.yview); self.lst.config(yscrollcommand=sc.set); sc.pack(side=tk.RIGHT, fill=tk.Y)
        pv_top=ttk.Frame(right); pv_top.pack(fill=tk.X)
        ttk.Label(pv_top, text=self.tr("preview")).pack(side=tk.LEFT)
        ttk.Button(pv_top, text=self.tr("decode_selected_preview"), command=self.on_preview_selected).pack(side=tk.RIGHT)
        self.preview_canvas=tk.Canvas(right, background="#111"); self.preview_canvas.pack(fill=tk.BOTH, expand=True)
        bot=ttk.Frame(frm); bot.pack(fill=tk.X, padx=8, pady=6)
        ttk.Label(bot, text=self.tr("output_dir")).pack(side=tk.LEFT)
        ttk.Entry(bot, textvariable=self.out_dir, width=60).pack(side=tk.LEFT, padx=6)
        ttk.Button(bot, text="…", command=self.on_choose_outdir).pack(side=tk.LEFT)

    def on_browse_afs(self):
        p=filedialog.askopenfilename(title=self.tr("pick_container"), filetypes=[("Containers","*.afs;*.bin;*.dat;*.pvm;*.tex;*.*")])
        if p: self.afs_path.set(p); self.lst.delete(0,tk.END); self.status.set(self.tr("loaded", path=p))

    def _load_afs(self):
        try:
            return AFSArchive(self.afs_path.get().strip())
        except Exception as e:
            self.status.set(f"AFS parse failed: {e}"); return None

    def on_scan_entries(self):
        self.lst.delete(0, tk.END); afs=self._load_afs()
        if not afs: return
        self._current_afs=afs
        for e in afs.entries: self.lst.insert(tk.END, f"#{e['index']:04d} off=0x{e['offset']:08X} size=0x{e['size']:06X}")
        self.status.set(self.tr("entries_n", n=len(afs.entries)))

    def on_extract_raw(self):
        afs=self._load_afs()
        if not afs: return
        out=pathlib.Path(self.out_dir.get() or "."); out.mkdir(parents=True, exist_ok=True)
        n=afs.extract_all(out); self.status.set(self.tr("extracted_n", n=n, out=out))

    
    
    def on_decode_sticker_auto(self):
        afs = self._load_afs()
        if not afs: 
            return
        self.status.set(self.tr("decoding_stickers"))
        self.update_idletasks()
        import pathlib
        out = pathlib.Path(self.out_dir.get() or ".") / (afs.path.stem + "_STICKER_DEC_v3")
        out.mkdir(parents=True, exist_ok=True)

        import numpy as np
        try:
            from PIL import Image
        except Exception:
            messagebox.showerror(self.tr("app_title"), "Pillow not installed.")
            return

        def part1by1(n:int)->int:
            n &= 0xFFFF
            n = (n | (n << 8)) & 0x00FF00FF
            n = (n | (n << 4)) & 0x0F0F0F0F
            n = (n | (n << 2)) & 0x33333333
            n = (n | (n << 1)) & 0x55555555
            return n
        def morton_yx(x:int,y:int)->int:
            return part1by1(y) | (part1by1(x) << 1)

        def pal_1555(hdr:bytes):
            pals=[]
            for i in range(0,32,2):
                c=int.from_bytes(hdr[i:i+2],'little')
                a=255 if ((c>>15)&1) else 0
                r=((c>>10)&0x1F)*255//31
                g=((c>>5)&0x1F)*255//31
                b=(c&0x1F)*255//31
                pals.append((r,g,b,a))
            return pals
        def pal_565(hdr:bytes):
            pals=[]
            for i in range(0,32,2):
                c=int.from_bytes(hdr[i:i+2],'little')
                r=((c>>11)&0x1F)*255//31
                g=((c>>5)&0x3F)*255//63
                b=(c&0x1F)*255//31
                pals.append((r,g,b,255))
            return pals
        def pal_4444(hdr:bytes):
            pals=[]
            for i in range(0,32,2):
                c=int.from_bytes(hdr[i:i+2],'little')
                a=((c>>12)&0xF)*17
                r=((c>>8)&0xF)*17
                g=((c>>4)&0xF)*17
                b=(c&0xF)*17
                pals.append((r,g,b,a))
            return pals
        def pal_5551(hdr:bytes):
            pals=[]
            for i in range(0,32,2):
                c=int.from_bytes(hdr[i:i+2],'little')
                a=255 if (c & 1) else 0
                r=((c>>11)&0x1F)*255//31
                g=((c>>6)&0x1F)*255//31
                b=((c>>1)&0x1F)*255//31
                pals.append((r,g,b,a))
            return pals
        PAL_MAP = {"4444":pal_4444,"1555":pal_1555,"565":pal_565,"5551":pal_5551}

        def decode_one(raw:bytes, palmode:str, even_high:bool=True):
            hdr, payload = raw[:32], raw[32:]
            if len(payload)!=2048: 
                return None
            pal = PAL_MAP[palmode](hdr)
            img = np.zeros((64,64,4), dtype=np.uint8)
            for y in range(64):
                for x in range(64):
                    m = morton_yx(x,y)
                    b = payload[m>>1]
                    if even_high:
                        idx = (b>>4)&0xF if (m & 1)==0 else (b & 0xF)
                    else:
                        idx = (b & 0xF) if (m & 1)==0 else ((b>>4)&0xF)
                    img[y,x] = pal[idx]
            return Image.fromarray(img, 'RGBA')

        def score_smooth(im:Image.Image)->float:
            g = np.array(im.convert("L"), dtype=np.float32)
            gx = np.abs(g[:,1:] - g[:,:-1]).mean()
            gy = np.abs(g[1:,:] - g[:-1,:]).mean()
            return gx + gy

        total=0
        with open(afs.path, "rb") as f:
            for e in afs.entries:
                if e["size"] != 2080 or e["offset"] <= 0: 
                    continue
                f.seek(e["offset"]); raw = f.read(e["size"])
                best_s=None; best_im=None
                for palmode in ("4444","1555","565","5551"):
                    for even_high in (True, False):
                        im = decode_one(raw, palmode, even_high)
                        s  = score_smooth(im)
                        if best_s is None or s < best_s:
                            best_s = s; best_im = im
                if best_im:
                    best_im.save(out / f"{e['index']:04d}.png"); total += 1

        # tilesheet
        files = sorted(out.glob("[0-9][0-9][0-9][0-9].png"))
        if files:
            W,H = Image.open(files[0]).size
            cols=10; rows=(len(files)+cols-1)//cols
            sheet = Image.new("RGBA",(W*cols,H*rows))
            for idx,p in enumerate(files):
                im = Image.open(p)
                r,c = divmod(idx, cols)
                sheet.paste(im,(c*W, r*H))
            sheet.save(out/"tilesheet.png")

        self.status.set(self.tr("decoded_stickers_n", n=total, out=str(out)))
        from tkinter import messagebox
        messagebox.showinfo(self.tr("app_title"), self.tr("decoded_stickers_n", n=total, out=str(out)))

    def on_full_deprs(self):

        path = self.afs_path.get().strip()
        if not path:
            messagebox.showwarning(self.tr("no_file"), self.tr("pick_container")); 
            return
        out = pathlib.Path(self.out_dir.get() or ".")
        out.mkdir(parents=True, exist_ok=True)
        try:
            res = full_deprs_and_scan(path, str(out))
            # show summary and where results live
            msg = f"PRS: {res.get('prs_blocks')}  |  PVR/PVP found: {res.get('pvr_found')}\n" \
                  f"DEPRS: {res.get('deprs_dir')}\n" \
                  f"PVR DIR: {res.get('pvr_dir')}"
            messagebox.showinfo("dePRS", msg)
            self.status.set(self.tr("scan_complete"))
        except Exception as e:
            messagebox.showerror("dePRS", str(e))

    def on_scan_pvrt(self):
            path=self.afs_path.get().strip()
            if not path: messagebox.showwarning(self.tr("no_file"), self.tr("pick_container")); return
            out=pathlib.Path(self.out_dir.get() or "."); out.mkdir(parents=True, exist_ok=True)
            try:
                # first attempt: scan the container directly for PVRT
                pypvr.Pypvr.Decode(args_str=f'"{path}" -o "{out}" -dbg')
    
                # after direct scan, check if any PVRT were emitted
                base = pathlib.Path(path).name
                ext_dir = pathlib.Path(out) / (base + "_EXT")
                pvr_dir = ext_dir / "PVR"
                found = pvr_dir.exists() and any(pvr_dir.glob("*.pvr"))
    
                # PRS fallback: if no PVRT found, try decompress PRS chunks into _DEPRS and scan that folder
                if not found:
                    raw = pathlib.Path(path).read_bytes()
                    deprs_dir = ext_dir / "_DEPRS"
                    n = prs_extract_all_to_folder(raw, str(deprs_dir), entry_label="prs")
                    if n:
                        # scan decompressed blobs recursively
                        pypvr.Pypvr.Decode(args_str=f'-scandir "{deprs_dir}" -o "{out}" -dbg')
                        # update pvr_dir check after decompress
                        found = pvr_dir.exists() and any(pvr_dir.glob("*.pvr"))
                # update status or warn depending on whether anything was found
                if found:
                    self.status.set(self.tr("scan_complete"))
                else:
                    self.status.set(self.tr("no_pvrt_found"))
                    messagebox.showinfo(self.tr("preview"), self.tr("no_pvrt_found"))
            except Exception as e:
                messagebox.showerror("PyPVR", str(e))
    
    def on_entry_select(self, _evt=None):
            pass
    
    def on_preview_selected(self):
            if Image is None: messagebox.showwarning("Pillow", self.tr("no_pillow")); return
            if not self._current_afs: messagebox.showwarning("AFS", self.tr("no_afs")); return
            sel=self.lst.curselection()
            if not sel: return
            idx=sel[0]; raw=self._current_afs.read_entry_bytes(idx)
            try:
                dec = pypvr.Pypvr.Decode(args_str='-buffer -fmt png -nolog', buff_pvr=raw, buff_pvp=None)
                img = dec.get_image_buffer()
                if img is None: raise RuntimeError("Not a PVR or decode failed.")
                self._show_preview(img); self.status.set(self.tr("preview_entry", idx=idx))
            except Exception as e:
                messagebox.showerror("Preview", f"#{idx}: {e}")
    
    def _show_preview(self, pil_img):
            c=self.preview_canvas; c.delete("all")
            cw,ch=c.winfo_width(), c.winfo_height()
            if cw<2 or ch<2: c.update_idletasks(); cw,ch=c.winfo_width(), c.winfo_height()
            iw,ih=pil_img.width, pil_img.height
            scale=min(cw/max(1,iw), ch/max(1,ih), 1.0)
            nw,nh=max(1,int(iw*scale)), max(1,int(ih*scale))
            if (nw,nh)!=(iw,ih): pil_img=pil_img.resize((nw,nh))
            self.preview_imgtk=ImageTk.PhotoImage(pil_img); c.create_image(cw//2, ch//2, image=self.preview_imgtk, anchor="center")
    
    def on_choose_outdir(self):
            d=filedialog.askdirectory(title=self.tr("select_output"))
            if d: self.out_dir.set(d)
    
        # PVR tab
    def build_tab_pvr(self):
            frm=self.tab_pvr
            # instruction label
            ttk.Label(frm, text=self.tr("pvr_help"), wraplength=650, justify=tk.LEFT, foreground="grey").pack(fill=tk.X, padx=8, pady=(4,2))
            r1=ttk.Frame(frm); r1.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(r1, text=self.tr("source_label")).pack(side=tk.LEFT)
            self.pvr_src=tk.StringVar(); ttk.Entry(r1, textvariable=self.pvr_src, width=60).pack(side=tk.LEFT, padx=6)
            ttk.Button(r1, text=self.tr("browse"), command=self.on_browse_any).pack(side=tk.LEFT)
            r2=ttk.Frame(frm); r2.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(r2, text=self.tr("output_label")).pack(side=tk.LEFT)
            self.pvr_out=tk.StringVar(value=str(Path.cwd()/ "pvr_out")); ttk.Entry(r2, textvariable=self.pvr_out, width=60).pack(side=tk.LEFT, padx=6)
            ttk.Button(r2, text="…", command=self.on_choose_pvr_out).pack(side=tk.LEFT)
            r3=ttk.Frame(frm); r3.pack(fill=tk.X, padx=8, pady=8)
            ttk.Button(r3, text=self.tr("decode_pvr"), command=self.on_decode_pvr).pack(side=tk.LEFT, padx=4)
            ttk.Button(r3, text=self.tr("encode_pvr"), command=self.on_encode_pvr).pack(side=tk.LEFT, padx=4)
            pv=ttk.Frame(frm); pv.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            self.file_list=tk.Listbox(pv, selectmode=tk.BROWSE); self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.file_list.bind("<<ListboxSelect>>", self.on_preview_file_select)
            sc=ttk.Scrollbar(pv, orient=tk.VERTICAL, command=self.file_list.yview); self.file_list.config(yscrollcommand=sc.set); sc.pack(side=tk.LEFT, fill=tk.Y)
            self.file_canvas=tk.Canvas(pv, background="#111"); self.file_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            r4=ttk.Frame(frm); r4.pack(fill=tk.X, padx=8, pady=6); ttk.Button(r4, text=self.tr("list_files"), command=self.on_list_files).pack(side=tk.LEFT)
    
    def on_browse_any(self):
            p=filedialog.askopenfilename(title=self.tr("source_label"), filetypes=[("All","*.*")])
            if p: self.pvr_src.set(p)
    def on_choose_pvr_out(self):
            d=filedialog.askdirectory(title=self.tr("select_output"))
            if d: self.pvr_out.set(d)
    def on_list_files(self):
            self.file_list.delete(0, tk.END); src=self.pvr_src.get().strip()
            if not src: return
            p=pathlib.Path(src)
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.suffix.lower() in (".pvr",".pvp",".png",".bmp",".gif",".tga",".jpg",".jpeg"):
                        self.file_list.insert(tk.END, str(f))
            else:
                self.file_list.insert(tk.END, str(p))
    def on_preview_file_select(self, _evt=None):
            if Image is None: return
            sel=self.file_list.curselection()
            if not sel: return
            p=pathlib.Path(self.file_list.get(sel[0]))
            try:
                if p.suffix.lower()==".pvr":
                    raw=p.read_bytes(); dec=pypvr.Pypvr.Decode(args_str='-buffer -fmt png -nolog', buff_pvr=raw, buff_pvp=None)
                    img=dec.get_image_buffer()
                else:
                    img=Image.open(p).convert("RGBA")
                self._show_file_preview(img)
            except Exception as e:
                messagebox.showerror("Preview", str(e))
    def _show_file_preview(self, img):
            c=self.file_canvas; c.delete("all")
            cw,ch=c.winfo_width(), c.winfo_height()
            if cw<2 or ch<2: c.update_idletasks(); cw,ch=c.winfo_width(), c.winfo_height()
            iw,ih=img.width, img.height
            scale=min(cw/max(1,iw), ch/max(1,ih), 1.0)
            nw,nh=max(1,int(iw*scale)), max(1,int(ih*scale))
            if (nw,nh)!=(iw,ih): img=img.resize((nw,nh))
            self._file_imgtk=ImageTk.PhotoImage(img); c.create_image(cw//2, ch//2, image=self._file_imgtk, anchor="center")
    def on_decode_pvr(self):
            src=self.pvr_src.get().strip(); out=self.pvr_out.get().strip() or "."
            if not src: messagebox.showwarning(self.tr("source_needed"), self.tr("src_pvr_needed")); return
            try:
                pypvr.Pypvr.Decode(args_str=f'"{src}" -o "{out}" -fmt png')
                self.status.set(self.tr("decode_complete"))
            except Exception as e:
                messagebox.showerror("Decode", str(e))
    def on_encode_pvr(self):
            src=self.pvr_src.get().strip(); out=self.pvr_out.get().strip() or "."
            if not src: messagebox.showwarning(self.tr("source_needed"), self.tr("src_png_needed")); return
            dlg=tk.Toplevel(self); dlg.title(self.tr("options_title")); dlg.grab_set()
            color=tk.StringVar(value="-1555"); tex=tk.StringVar(value="-tw")
            mm=tk.BooleanVar(value=False); flip=tk.BooleanVar(value=False); gi=tk.StringVar(value="0")
            form=ttk.Frame(dlg); form.pack(padx=10, pady=10)
            ttk.Label(form, text=self.tr("color")).grid(row=0,column=0,sticky="e")
            ttk.Combobox(form, textvariable=color, values=["-1555","-4444","-565","-8888","-p4bpp","-p8bpp"], state="readonly").grid(row=0,column=1)
            ttk.Label(form, text=self.tr("texture")).grid(row=1,column=0,sticky="e")
            ttk.Combobox(form, textvariable=tex, values=["-tw","-pal4","-pal8","-re","-twre","-vq","-svq"], state="readonly").grid(row=1,column=1)
            ttk.Checkbutton(form, text=self.tr("mm"), variable=mm).grid(row=2,column=1,sticky="w")
            ttk.Checkbutton(form, text=self.tr("flip"), variable=flip).grid(row=3,column=1,sticky="w")
            ttk.Label(form, text=self.tr("gbix")).grid(row=4,column=0,sticky="e"); ttk.Entry(form, textvariable=gi, width=10).grid(row=4,column=1,sticky="w")
            btns=ttk.Frame(dlg); btns.pack(padx=10, pady=8, fill=tk.X)
            ttk.Button(btns, text=self.tr("encode"), command=lambda: self._do_encode_close(dlg, src, out, color.get(), tex.get(), mm.get(), flip.get(), gi.get())).pack(side=tk.RIGHT)
            ttk.Button(btns, text=self.tr("cancel"), command=dlg.destroy).pack(side=tk.RIGHT, padx=6)
    def _do_encode_close(self, dlg, src, out, color, tex, mm, flip, gi):
            try:
                args=f'"{src}" -o "{out}" {color} {tex}'
                if mm: args+=" -mm"
                if flip: args+=" -flip"
                if gi and gi.isdigit(): args+=f" -gi {gi}"
                pypvr.Pypvr.Encode(args_str=args)
                self.status.set(self.tr("encode_complete"))
            except Exception as e:
                messagebox.showerror("Encode", str(e))
            finally:
                dlg.destroy()
    
        # Repack tab
    def build_tab_repack(self):
            frm=self.tab_repack
            # instruction label
            ttk.Label(frm, text=self.tr("repack_help"), wraplength=650, justify=tk.LEFT, foreground="grey").pack(fill=tk.X, padx=8, pady=(4,2))
            top=ttk.Frame(frm); top.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(top, text=self.tr("src_afs_needed")).pack(side=tk.LEFT)
            self.repack_src=tk.StringVar(); ttk.Entry(top, textvariable=self.repack_src, width=60).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text=self.tr("browse"), command=lambda: self._browse_to(self.repack_src)).pack(side=tk.LEFT)
            ttk.Button(top, text=self.tr("load_entries"), command=self.on_load_repack_entries).pack(side=tk.LEFT, padx=8)
            main=ttk.Panedwindow(frm, orient=tk.HORIZONTAL); main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            left=ttk.Frame(main); right=ttk.Frame(main); main.add(left, weight=2); main.add(right, weight=3)
            self.map_list=tk.Listbox(left, selectmode=tk.SINGLE); self.map_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sc=ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.map_list.yview); self.map_list.config(yscrollcommand=sc.set); sc.pack(side=tk.RIGHT, fill=tk.Y)
            btns=ttk.Frame(right); btns.pack(fill=tk.Y, expand=True)
            ttk.Button(btns, text=self.tr("set_replacement"), command=self.on_set_replacement).pack(fill=tk.X, pady=4)
            ttk.Button(btns, text=self.tr("clear_replacement"), command=self.on_clear_replacement).pack(fill=tk.X, pady=4)
            ttk.Separator(btns).pack(fill=tk.X, pady=8)
            ttk.Label(btns, text=self.tr("output_afs")).pack(anchor="w")
            self.repack_out=tk.StringVar(value=str(Path.cwd()/ "patched.AFS"))
            ttk.Entry(btns, textvariable=self.repack_out, width=50).pack(fill=tk.X, pady=4)
            ttk.Button(btns, text=self.tr("choose"), command=lambda: self._choose_save(self.repack_out)).pack()
            ttk.Separator(btns).pack(fill=tk.X, pady=8)
            ttk.Button(btns, text=self.tr("write_new_afs"), command=self.on_write_repack).pack(fill=tk.X, pady=8)
    def _browse_to(self, var):
            p=filedialog.askopenfilename(title=self.tr("src_afs_needed"), filetypes=[("AFS files","*.afs;*.AFS"),("All","*.*")])
            if p: var.set(p)
    def _choose_save(self, var):
            p=filedialog.asksaveasfilename(title=self.tr("choose"), defaultextension=".AFS", filetypes=[("AFS","*.AFS")])
            if p: var.set(p)
    def on_load_repack_entries(self):
            self.map_list.delete(0, tk.END); p=self.repack_src.get().strip()
            if not p: return
            try:
                self._current_afs=AFSArchive(p)
            except Exception as e:
                messagebox.showerror("AFS", str(e)); return
            for e in self._current_afs.entries:
                tag=f"#{e['index']:04d} off=0x{e['offset']:08X} size=0x{e['size']:06X}"
                if e['index'] in self.replacements: tag += "  → " + os.path.basename(self.replacements[e['index']])
                self.map_list.insert(tk.END, tag)
            self.status.set(self.tr("entries_n", n=len(self._current_afs.entries)))
    def on_set_replacement(self):
            sel=self.map_list.curselection()
            if not sel: return
            idx=sel[0]; f=filedialog.askopenfilename(title=self.tr("set_replacement"))
            if f: self.replacements[idx]=f; self.on_load_repack_entries()
    def on_clear_replacement(self):
            sel=self.map_list.curselection()
            if not sel: return
            idx=sel[0]
            if idx in self.replacements: del self.replacements[idx]; self.on_load_repack_entries()
    def on_write_repack(self):
            if not self._current_afs: messagebox.showwarning("AFS", self.tr("src_afs_needed")); return
            if not self.replacements: messagebox.showwarning("AFS", self.tr("no_replacements")); return
            outp=self.repack_out.get().strip()
            try:
                dst=self._current_afs.replace_in_place(self.replacements, pathlib.Path(outp))
                self.status.set(self.tr("done")); messagebox.showinfo(self.tr("done"), self.tr("repack_saved", dst=dst))
            except Exception as e:
                messagebox.showerror(self.tr("repack_failed"), str(e))
    
        # Recipes tab
    def build_tab_recipes(self):
            frm=self.tab_recipes
            # instruction label
            ttk.Label(frm, text=self.tr("recipes_help"), wraplength=650, justify=tk.LEFT, foreground="grey").pack(fill=tk.X, padx=8, pady=(4,2))
            g1=ttk.LabelFrame(frm, text=self.tr("recipes_r1")); g1.pack(fill=tk.X, padx=8, pady=8)
            ttk.Label(g1, text=self.tr("container_label")).grid(row=0,column=0,sticky="e", padx=4, pady=4)
            self.rc1_in=tk.StringVar(); ttk.Entry(g1, textvariable=self.rc1_in, width=60).grid(row=0,column=1,sticky="we")
            ttk.Button(g1, text=self.tr("browse"), command=lambda: self._browse_to(self.rc1_in)).grid(row=0,column=2,padx=6)
            ttk.Label(g1, text=self.tr("output_label")).grid(row=1,column=0,sticky="e", padx=4, pady=4)
            self.rc1_out=tk.StringVar(value=str(Path.cwd()/ "rc1_out")); ttk.Entry(g1, textvariable=self.rc1_out, width=60).grid(row=1,column=1,sticky="we")
            ttk.Button(g1, text="…", command=lambda: self._choose_dir(self.rc1_out)).grid(row=1,column=2,padx=6)
            ttk.Button(g1, text=self.tr("recipes_r1_run"), command=self.recipe1_run).grid(row=0,column=3,rowspan=2,padx=8)
            g2=ttk.LabelFrame(frm, text=self.tr("recipes_r2")); g2.pack(fill=tk.X, padx=8, pady=8)
            ttk.Label(g2, text="pvr_log.txt:").grid(row=0,column=0,sticky="e", padx=4, pady=4)
            self.rc2_log=tk.StringVar(); ttk.Entry(g2, textvariable=self.rc2_log, width=60).grid(row=0,column=1,sticky="we")
            ttk.Button(g2, text=self.tr("browse"), command=lambda: self._browse_to(self.rc2_log)).grid(row=0,column=2,padx=6)
            ttk.Button(g2, text=self.tr("recipes_r2_run"), command=self.recipe2_run).grid(row=0,column=3,padx=8)
            g3=ttk.LabelFrame(frm, text=self.tr("recipes_r3")); g3.pack(fill=tk.X, padx=8, pady=8)
            ttk.Label(g3, text="pvr_log.txt:").grid(row=0,column=0,sticky="e", padx=4, pady=4)
            self.rc3_log=tk.StringVar(); ttk.Entry(g3, textvariable=self.rc3_log, width=60).grid(row=0,column=1,sticky="we")
            ttk.Button(g3, text=self.tr("browse"), command=lambda: self._browse_to(self.rc3_log)).grid(row=0,column=2,padx=6)
            ttk.Label(g3, text=self.tr("output_label")).grid(row=1,column=0,sticky="e", padx=4, pady=4)
            self.rc3_out=tk.StringVar(value=str(Path.cwd()/ "rc3_pvr")); ttk.Entry(g3, textvariable=self.rc3_out, width=60).grid(row=1,column=1,sticky="we")
            ttk.Button(g3, text="…", command=lambda: self._choose_dir(self.rc3_out)).grid(row=1,column=2,padx=6)
            ttk.Button(g3, text=self.tr("recipes_r3_run"), command=self.recipe3_run).grid(row=0,column=3,rowspan=2,padx=8)
    def _choose_dir(self, var):
            d=filedialog.askdirectory(title=self.tr("select_output"))
            if d: var.set(d)
    def recipe1_run(self):
            src=self.rc1_in.get().strip(); out=self.rc1_out.get().strip()
            if not src: messagebox.showwarning(self.tr("no_file"), self.tr("pick_container")); return
            pathlib.Path(out).mkdir(parents=True, exist_ok=True)
            try:
                pypvr.Pypvr.Decode(args_str=f'"{src}" -o "{out}" -fmt png -dbg')
                self.status.set(self.tr("scan_complete")); messagebox.showinfo("OK", self.tr("scan_complete"))
            except Exception as e:
                messagebox.showerror("Recipe 1", str(e))
    def recipe2_run(self):
            log=self.rc2_log.get().strip()
            if not log: messagebox.showwarning("Log", self.tr("pick_log")); return
            if not os.path.exists(log): messagebox.showerror("Log","File not found"); return
            try:
                pypvr.Pypvr.Cli(args=[log])  # leave PyPVR CLI passthrough if your script expects this
                self.status.set(self.tr("reimport_done")); messagebox.showinfo("OK", self.tr("reimport_done"))
            except Exception as e:
                messagebox.showerror("Recipe 2", str(e))
    def recipe3_run(self):
            log=self.rc3_log.get().strip(); out=self.rc3_out.get().strip()
            if not log: messagebox.showwarning("Log", self.tr("pick_log")); return
            pathlib.Path(out).mkdir(parents=True, exist_ok=True)
            try:
                pypvr.Pypvr.Cli(args=[log, "-o", out])
                self.status.set(self.tr("encode_only")); messagebox.showinfo("OK", self.tr("encode_only"))
            except Exception as e:
                messagebox.showerror("Recipe 3", str(e))

def main():
    app=App(); app.mainloop()

if __name__=="__main__":
    main()

# ====== FINAL PATCH BLOCK (appended) ======

# Robust AFS reader supporting embedded AFS and sector-sized tables
class __PatchedAFSArchive:
    def __init__(self, path):
        from pathlib import Path as _P
        self.path=_P(path); self.entries=[]; self.base=0
        self._read()

    @staticmethod
    def _u32(b,o): return int.from_bytes(b[o:o+4], "little")
    @staticmethod
    def _ok(total, off, size): return (0 <= off < total) and (0 < size <= total - off)

    def _read(self):
        data=self.path.read_bytes(); total=len(data)
        pos=data.find(b"AFS\x00")
        if pos==-1: raise ValueError("AFS not found")
        n=self._u32(data, pos+4); table=pos+12
        pairs=[(self._u32(data, table+i*8+0), self._u32(data, table+i*8+4)) for i in range(n)]
        cand=[]
        for mode in ("a_abs","b_abs","a_rel","b_rel"):
            for mul_off in (1,2048):
                for mul_sz in (1,2048):
                    ok=0; ent=[]
                    for i,(a,b) in enumerate(pairs):
                        if   mode=="a_abs": off,size=a*mul_off, b*mul_sz
                        elif mode=="b_abs": off,size=b*mul_off, a*mul_sz
                        elif mode=="a_rel": off,size=pos + a*mul_off, b*mul_sz
                        else:               off,size=pos + b*mul_off, a*mul_sz
                        if self._ok(total, off, size): ok+=1
                        ent.append({"index":i,"offset":off,"size":size})
                    cand.append((ok, ent))
        cand.sort(key=lambda x:x[0], reverse=True)
        best=cand[0][1]
        self.entries=[e for e in best if self._ok(total, e["offset"], e["size"])]
        self.base=pos

    def read_entry_bytes(self, idx):
        e = self.entries[idx]
        with open(self.path, "rb") as f:
            f.seek(e["offset"])
            return f.read(e["size"])

    def extract_all(self, out_dir):
        from pathlib import Path as _P
        out=_P(out_dir); out.mkdir(parents=True, exist_ok=True); n=0
        with open(self.path, "rb") as f:
            for e in self.entries:
                f.seek(e["offset"]); (out/f"{e['index']:04d}.bin").write_bytes(f.read(e["size"])); n+=1
        return n

# DePRS + PVRT scan (base + leaves) with GBIX inclusion
def __patched_full_deprs_and_scan(input_path: str, out_dir: str, max_depth: int = 6):
    import re
    from pathlib import Path as _P
    def _u32(b,o): return int.from_bytes(b[o:o+4],'little')
    def _scan(buf: bytes, out: _P, tag: str, origin: str):
        out.mkdir(parents=True, exist_ok=True); L=len(buf); c={"pvr":0,"pvp":0}
        def _maybe_gbix(start):
            look=max(0,start-32); g=buf.rfind(b"GBIX", look, start)
            if g!=-1 and g+8<=L:
                try:
                    n=_u32(buf,g+4)
                    if g+8+n==start: return g
                except: pass
            return start
        for m in re.finditer(b"PVRT", buf):
            pos=m.start()
            if pos+8<=L:
                size=_u32(buf,pos+4)+8
                if 0<size<=L-pos:
                    st=_maybe_gbix(pos); (out/f"{tag}_{origin}_pvrt_{pos:08X}.pvr").write_bytes(buf[st:pos+size]); c["pvr"]+=1
        for m in re.finditer(b"PVPL", buf):
            pos=m.start()
            if pos+8<=L:
                size=_u32(buf,pos+4)+8
                if 0<size<=L-pos:
                    (out/f"{tag}_{origin}_pvpl_{pos:08X}.pvp").write_bytes(buf[pos:pos+size]); c["pvp"]+=1
        return c

    p_in=_P(input_path); p_out=_P(out_dir); p_out.mkdir(parents=True, exist_ok=True)
    data=p_in.read_bytes(); base=p_in.stem
    ddir=p_out/f"{base}_DEPRS"; sdir=p_out/f"{base}_DEPRS_PVR"; ddir.mkdir(exist_ok=True); sdir.mkdir(exist_ok=True)

    c_base=_scan(data, sdir, base, "base")

    leaves=[]
    def _prs(buf,pos):
        try:
            out,used=_prs_decompress_auto(buf,pos)
            if out and used: return out,used
        except Exception: pass
        return None,None

    import re
    def rec(buf, tag, d):
        found=False
        for m in re.finditer(b"PRS", buf):
            found=True
            pos=m.start(); out,used=_prs(buf,pos)
            if out:
                name=f"{tag}_d{d}_@{pos:08X}"; (ddir/f"{name}.bin").write_bytes(out)
                if d<max_depth and b"PRS" in out: rec(out, name, d+1)
                else: leaves.append((name,out))
        if not found:
            leaves.append((f"{tag}_raw", buf))
    rec(data, base, 0)

    c_leaf={"pvr":0,"pvp":0}
    for name,buf in leaves:
        r=_scan(buf, sdir, name, "leaf")
        c_leaf["pvr"]+=r["pvr"]; c_leaf["pvp"]+=r["pvp"]

    total=c_base["pvr"]+c_base["pvp"]+c_leaf["pvr"]+c_leaf["pvp"]
    if total>0:
        try:
            pypvr.Pypvr.Decode(args_str=f'-scandir "{sdir}" -o "{p_out}" -fmt png -nolog')
        except Exception: pass

    return {"prs_blocks": len(list(re.finditer(b"PRS", data))),
            "base_pvr": c_base["pvr"], "base_pvp": c_base["pvp"],
            "leaf_pvr": c_leaf["pvr"], "leaf_pvp": c_leaf["pvp"],
            "total_pvrpvp": total, "deprs_dir": str(ddir), "pvr_dir": str(sdir)}

# Monkey-patch App to use robust AFS + fallback PVRT list + detailed dePRS report
try:
    App  # ensure class exists
    
except Exception:
    pass
def __patched_on_scan_entries(self):
        from pathlib import Path as _P
        import re, tkinter as tk
        path = self.afs_path.get().strip()
        # очистим левый список (Listbox), если он есть
        try:
            self.lst.delete(0, tk.END)
        except Exception:
            pass
        if not path:
            messagebox.showwarning(self.tr("no_file"), self.tr("pick_container")); return
        try:
            afs = __PatchedAFSArchive(path); self._current_afs = afs
            for e in afs.entries:
                self.lst.insert(
                    tk.END,
                    f"#{e['index']:04d} off=0x{e['offset']:08X} size=0x{e['size']:06X}"
                )
            self.status.set(self.tr("scan_ok"))
        except Exception as e:
            # Фоллбэк: нет AFS — покажем найденные PVRT/PVPL как «виртуальные» записи
            try:
                buf = _P(path).read_bytes()
                def _u32(b, o): return int.from_bytes(b[o:o+4], 'little')
                idx = 0
                for tag in ("PVRT", "PVPL"):
                    for m in re.finditer(tag.encode(), buf):
                        pos = m.start()
                        if pos + 8 <= len(buf):
                            size = _u32(buf, pos+4) + 8
                            if 0 < size <= len(buf) - pos:
                                name = f"{tag}_{idx:04d}."+("pvr" if tag=="PVRT" else "pvp")
                                self.lst.insert(
                                    tk.END,
                                    f"#{idx:04d} off=0x{pos:08X} size=0x{size:06X} {name}"
                                )
                                idx += 1
                self._current_afs = None
                if idx == 0:
                    self.status.set(self.tr("no_afs_try_deprs"))
                else:
                    self.status.set(self.tr("pvrt_fallback_listed"))
            except Exception as ee:
                self.status.set(f"{self.tr('scan_fail')}: {ee}")

def __patched_on_full_deprs(self):
        path=self.afs_path.get().strip()
        out=self.out_dir.get().strip() or str(Path(path).with_name("extracted"))
        res=__patched_full_deprs_and_scan(path, out)
        msg=(f"PRS найдено: {res.get('prs_blocks')}\\n"
             f"PVR/PVP в базе: {res.get('base_pvr')} / {res.get('base_pvp')}\\n"
             f"PVR/PVP в распакованных слоях: {res.get('leaf_pvr')} / {res.get('leaf_pvp')}\\n"
             f"ИТОГО PVR/PVP: {res.get('total_pvrpvp')}\\n"
             f"DEPRS: {res.get('deprs_dir')}\\n"
             f"PVR DIR: {res.get('pvr_dir')}")
        messagebox.showinfo("dePRS", msg)

try:
    App.on_scan_entries = __patched_on_scan_entries
    App.on_full_deprs   = __patched_on_full_deprs
except NameError:
    pass

# Inject i18n strings if missing
try:
    I18N
    for loc, pairs in {
        "ru": {
            "scan_ok":"Таблица AFS загружена",
            "scan_fail":"Ошибка сканирования",
            "no_afs_try_deprs":"AFS не найден. Используйте «Найти PVRT» или «Полный dePRS».",
            "pvrt_fallback_listed":"AFS нет — найдены PVRT/PVPL и показаны списком.",
            "afs_help":"Шаги: 1) Выберите контейнер (.afs/.bin/.dat): поддерживаются вложенные AFS и PRS‑обёртки. 2) «Сканировать записи» — если найден AFS, появится таблица. 3) «Извлечь RAW» — сохранит все записи как *.bin. 4) «Найти PVRT/палитры» — поиск PVR/PVP в любом файле (база + распакованные слои). 5) «Полный dePRS → поиск PVRT» — распаковать PRS и просканировать всё. Если AFS не найден — это нормально: используйте поиск PVRT или Full dePRS."
        },
        "en": {
            "scan_ok":"AFS table loaded",
            "scan_fail":"Scan error",
            "no_afs_try_deprs":"No AFS. Use ‘Find PVRT’ or ‘Full dePRS’.",
            "pvrt_fallback_listed":"No AFS — PVRT/PVPL entries are listed.",
            "afs_help":"Steps: 1) Pick a container (.afs/.bin/.dat): embedded AFS and PRS-wrapped files are supported. 2) “Scan entries” shows AFS table when present. 3) “Extract RAW” dumps all entries as *.bin. 4) “Find PVRT/Palettes” searches PVR/PVP in any file (base + dePRS layers). 5) “Full dePRS → PVRT scan” unpacks PRS and scans everything. If no AFS is found, that’s normal for .bin/.dat."
        }
    }.items():
        if loc in I18N:
            for k,v in pairs.items():
                I18N[loc].setdefault(k, v)
except Exception:
    pass

# ====== END PATCH BLOCK ======


# ====== ROBUST PVRT/PVPL SCAN PATCH (size heuristics, GBIX merge, next-header bound) ======
def __pvrt_guess_size(buf: bytes, pos: int):
    """Return a safe (start, size) for the PVRT chunk at pos.
       Strategy: prefer header size; if invalid -> use width/height/format heuristic;
       maximum bounded by next header (PVRT/PVPL/GBIX) or EOF."""
    import re, struct
    L = len(buf)

    def u16(o): 
        if o+2<=L: return int.from_bytes(buf[o:o+2],'little')
        return 0
    def u32(o): 
        if o+4<=L: return int.from_bytes(buf[o:o+4],'little')
        return 0

    # 1) try native size field
    size = u32(pos+4) + 8
    if 0 < size <= L - pos:
        return pos, size

    # 2) parse width/height and formats to estimate data size
    px = buf[pos+8] if pos+9<=L else 0
    tx = buf[pos+9] if pos+10<=L else 0
    w  = u16(pos+12); h = u16(pos+14)
    # sanity
    if not (4 <= w <= 2048 and 4 <= h <= 2048):
        # give up: bound by next header or EOF
        nxt = min([i for i in [buf.find(b"PVRT", pos+4), buf.find(b"PVPL", pos+4), buf.find(b"GBIX", pos+4)] if i!=-1] or [L])
        return pos, max(0, min(L - pos, nxt - pos))
    # estimate bytes after header (data only)
    bpp_guess = 2  # default direct-color 16bpp
    data_guess = None
    # texture mode rough groups (see PyPVR)
    pal4 = {5,6}
    pal8 = {7,8}
    vq   = {3,4,16,17}
    rect = {9,10,11,12,14,15,18}
    if tx in pal4:
        data_guess = (w*h)//2
    elif tx in pal8:
        data_guess = (w*h)
    elif tx in vq:
        # indices + codebook (heuristic); add mips slack
        indices = (w*h)//4
        codebook = 2048  # typical
        data_guess = indices + codebook + 0x800  # slack for mips
    elif tx in rect:
        # rectangle/stride/bmp; use px to decide 16 or 32 bpp
        if px in (7,14,18):
            bpp_guess = 4
        data_guess = w*h*bpp_guess
    else:
        data_guess = w*h*bpp_guess
    est_size = 0x10 + data_guess  # header ~16 bytes
    # 3) bound by next header if any
    nxt = min([i for i in [buf.find(b"PVRT", pos+4), buf.find(b"PVPL", pos+4), buf.find(b"GBIX", pos+4)] if i!=-1] or [L])
    size = min(est_size, L - pos, nxt - pos if nxt>pos else L - pos)
    # sanity lower bound
    if size < 0x20: size = min(L - pos, (nxt - pos) if nxt>pos else (L - pos))
    return pos, size

def __pvpl_guess_size(buf: bytes, pos: int):
    L=len(buf)
    def u16(o): 
        if o+2<=L: return int.from_bytes(buf[o:o+2],'little')
        return 0
    def u32(o): 
        if o+4<=L: return int.from_bytes(buf[o:o+4],'little')
        return 0
    size = u32(pos+4) + 8
    if 0 < size <= L - pos:
        return pos, size
    # fallback: read palette entries*bytes
    entries = u16(pos+0x0E)
    if entries in (0x10, 0x100):
        # mode at +0x08 (1=565,2=4444,6=8888)
        mode = buf[pos+0x08] if pos+0x09<=L else 0
        per = 4 if mode==6 else 2  # bytes per color
        payload = entries * per
        size = 0x10 + payload
    else:
        size = 0x40  # minimal
    nxt = min([i for i in [buf.find(b"PVRT", pos+4), buf.find(b"PVPL", pos+4), buf.find(b"GBIX", pos+4)] if i!=-1] or [L])
    size = min(size, L - pos, nxt - pos if nxt>pos else L-pos)
    if size < 0x10: size = min(L - pos, (nxt - pos) if nxt>pos else (L-pos))
    return pos, size

def __maybe_gbix_start(buf: bytes, start: int):
    """If GBIX is immediately before PVRT (GBIX + 8 + length == PVRT), include it."""
    L=len(buf)
    def u32(o): 
        if o+4<=L: return int.from_bytes(buf[o:o+4],'little')
        return 0
    look=max(0, start-32)
    g=buf.rfind(b"GBIX", look, start)
    if g!=-1 and g+8<=L:
        try:
            n=u32(g+4)
            if g+8+n==start: return g
        except: pass
    return start

def robust_scan_to_dir(in_bytes: bytes, out_dir: str, tag: str, origin: str):
    """Improved scanner used by Full dePRS and 'Find PVRT'.
       Writes .pvr/.pvp with GBIX merge; returns counters."""
    import os, re
    from pathlib import Path as _P
    out=_P(out_dir); out.mkdir(parents=True, exist_ok=True)
    c={"pvr":0,"pvp":0}
    # PVRT scanning (Dreamcast PowerVR textures)
    for m in re.finditer(b"PVRT", in_bytes):
        pos = m.start()
        st, sz = __pvrt_guess_size(in_bytes, pos)
        if sz > 0:
            # include GBIX if adjacent
            (_P(out) / f"{tag}_{origin}_pvrt_{pos:08X}.pvr").write_bytes(
                in_bytes[__maybe_gbix_start(in_bytes, st):pos + sz]
            )
            c["pvr"] += 1

    # PVPL scanning (palette blocks)
    for m in re.finditer(b"PVPL", in_bytes):
        pos = m.start()
        st, sz = __pvpl_guess_size(in_bytes, pos)
        if sz > 0:
            (_P(out) / f"{tag}_{origin}_pvpl_{pos:08X}.pvp").write_bytes(in_bytes[pos:pos + sz])
            c["pvp"] += 1

    # TIM2/TM2F scanning (PlayStation 2 TIM2 textures)
    # These signatures mark PS2 texture containers used in games like Tokyo Xtreme Racer 0/3.
    # We search for either 'TIM2' or 'TM2F' and extract until the next known header or EOF.
    for sig in (b"TIM2", b"TM2F"):
        for m in re.finditer(sig, in_bytes):
            pos = m.start()
            # Determine end by finding the nearest next header (TIM2/TM2F/PVRT/PVPL/GBIX/PRS/AFS)
            next_positions = []
            for hdr in (b"TIM2", b"TM2F", b"PVRT", b"PVPL", b"GBIX", b"PRS", b"AFS"):
                i = in_bytes.find(hdr, pos + 4)
                if i != -1:
                    next_positions.append(i)
            end = min(next_positions) if next_positions else len(in_bytes)
            # sanity: minimal 0x80 bytes to avoid too short segments
            size = end - pos
            if size >= 0x80:
                ext = "tm2" if sig == b"TIM2" else "tm2f"
                try:
                    (_P(out) / f"{tag}_{origin}_{ext}_{pos:08X}.{ext}").write_bytes(in_bytes[pos:pos + size])
                    c.setdefault(ext, 0)
                    c[ext] += 1
                except Exception:
                    pass

    # PVM/PVMH scanning (Sega Dreamcast/Naomi texture archives)
    # Some Dreamcast and Naomi titles bundle multiple PVR textures in PVM/GVM containers.
    # We search for the 'PVMH' or 'GVMH' signature and extract until the next known header.
    for sig in (b"PVMH", b"GVMH"):
        for m in re.finditer(sig, in_bytes):
            pos = m.start()
            next_positions = []
            for hdr in (b"PVMH", b"GVMH", b"TIM2", b"TM2F", b"PVRT", b"PVPL", b"GBIX", b"PRS", b"AFS"):
                i = in_bytes.find(hdr, pos + 4)
                if i != -1:
                    next_positions.append(i)
            end = min(next_positions) if next_positions else len(in_bytes)
            size = end - pos
            if size >= 0x80:
                ext = "pvm" if sig == b"PVMH" else "gvm"
                try:
                    (_P(out) / f"{tag}_{origin}_{ext}_{pos:08X}.{ext}").write_bytes(in_bytes[pos:pos + size])
                    c.setdefault(ext, 0)
                    c[ext] += 1
                except Exception:
                    pass

    return c


# (monkey patch removed in modular version)