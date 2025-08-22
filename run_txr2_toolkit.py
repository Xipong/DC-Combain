#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TXR2 Toolkit — strong launcher (no relative-import or UnboundLocal traps)."""
import sys, os
from pathlib import Path
from importlib import util as importlib_util  # avoid 'importlib' name inside function

def main():
    base = Path(__file__).resolve().parent
    pkg = base / "txr2_toolkit_modular"
    # prefer package path
    if pkg.exists():
        sys.path.insert(0, str(pkg))
        spec = importlib_util.spec_from_file_location("txr2_toolkit_modular.__main__", pkg / "__main__.py")
        mod = importlib_util.module_from_spec(spec)
        sys.modules["txr2_toolkit_modular.__main__"] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "main") and callable(mod.main):
            return mod.main()
        # fallback: directly import gui_app
        spec2 = importlib_util.spec_from_file_location("gui_app", pkg / "gui_app.py")
        mod2 = importlib_util.module_from_spec(spec2)
        spec2.loader.exec_module(mod2)
        if hasattr(mod2, "main") and callable(mod2.main):
            return mod2.main()
        if hasattr(mod2, "App"):
            app = mod2.App(); app.mainloop(); return
        raise SystemExit("gui_app: no main() or App found")
    # fallback: loose files next to launcher
    cand = base
    if (cand/"gui_app.py").exists() and (cand/"scanners.py").exists():
        sys.path.insert(0, str(cand))
        spec = importlib_util.spec_from_file_location("gui_app", cand/"gui_app.py")
        mod = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "main") and callable(mod.main):
            return mod.main()
        if hasattr(mod, "App"):
            app = mod.App(); app.mainloop(); return
    raise SystemExit("Не найдены модули: txr2_toolkit_modular/ или gui_app.py рядом с запускалкой.")

if __name__ == "__main__":
    main()
