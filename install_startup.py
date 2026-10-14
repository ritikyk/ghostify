"""
install_startup.py
Drops a silent VBScript into the Windows Startup folder.
file_browser.py will then launch automatically on every login.
No admin. No Task Scheduler.

Usage:
  python install_startup.py           # install
  python install_startup.py --remove  # uninstall
"""

import os
import sys
import subprocess
from pathlib import Path

SCRIPT   = Path(__file__).parent.resolve() / "file_browser.py"
STARTUP  = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
VBS_FILE = STARTUP / "ghostify_browser.vbs"
PYTHON   = sys.executable

VBS = f'Set s=CreateObject("WScript.Shell"):s.Run """{PYTHON}"" ""{SCRIPT}""",0,False'

def install():
    VBS_FILE.write_text(VBS)
    print(f"[OK] Installed → {VBS_FILE}")
    print(f"     Runs on every login silently.")
    print(f"     Remove: python install_startup.py --remove")
    ans = input("\nStart server right now? [y/n]: ").strip().lower()
    if ans == 'y':
        subprocess.Popen([PYTHON, str(SCRIPT)], creationflags=0x00000010)
        print("[OK] Server started.")

def remove():
    if VBS_FILE.exists():
        VBS_FILE.unlink()
        print(f"[OK] Removed: {VBS_FILE}")
    else:
        print("Not installed.")

if __name__ == "__main__":
    if "--remove" in sys.argv: remove()
    else: install()
