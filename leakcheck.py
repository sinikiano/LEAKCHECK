"""
LEAKCHECK — Entry Point
Checks for updates, then launches the GUI.
Developed by BionicSailor  |  Telegram: @BionicSailor
"""

import os
import sys

# ── Fix Tcl/Tk paths for PyInstaller onefile builds ──
# Must run BEFORE any tkinter import.  Set env-vars to the exact
# directory names that PyInstaller's runtime hook uses (_tcl_data / _tk_data).
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
    _tcl = os.path.join(_base, '_tcl_data')
    _tk  = os.path.join(_base, '_tk_data')
    if os.path.isdir(_tcl):
        os.environ['TCL_LIBRARY'] = _tcl
    if os.path.isdir(_tk):
        os.environ['TK_LIBRARY'] = _tk


def main():
    from gui import LeakCheckApp
    app = LeakCheckApp()
    app.mainloop()


if __name__ == "__main__":
    main()
