# Entry point that works both as package and as a script
import sys
from pathlib import Path
from importlib import util as importlib_util

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

def _load_gui_module():
    spec = importlib_util.spec_from_file_location("gui_app", BASE / "gui_app.py")
    mod = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

try:
    # absolute import inside package dir
    import gui_app as _gui
    main = getattr(_gui, "main", None)
except ImportError:
    _gui = _load_gui_module()
    main = getattr(_gui, "main", None)

if __name__ == "__main__":
    if callable(main):
        main()
    else:
        if hasattr(_gui, "App"):
            app = _gui.App()
            app.mainloop()
        else:
            raise SystemExit("gui_app: no main() or App found")
