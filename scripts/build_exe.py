"""
Build script to compile distributable_patcher.py into a standalone Windows executable (.exe).
"""

import sys
import subprocess
from pathlib import Path


def build():
    print("Checking PyInstaller...")
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    root_dir = Path(__file__).resolve().parent.parent
    patcher_script = root_dir / "scripts" / "distributable_patcher.py"
    
    print(f"Building standalone executable from: {patcher_script}")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "Rosario_Vampire_Patcher",
        "--paths", str(root_dir / "scripts"),
        str(patcher_script)
    ]
    
    subprocess.check_call(cmd, cwd=str(root_dir))
    
    dist_exe = root_dir / "dist" / "Rosario_Vampire_Patcher.exe"
    if dist_exe.exists():
        print(f"\n=======================================================")
        print(f"SUCCESS: Executable created at:")
        print(f"  {dist_exe.resolve()}")
        print(f"Distribute this .exe along with the 'translations/' folder!")
        print(f"=======================================================")
    else:
        print("Build completed. Check dist/ directory.")


if __name__ == "__main__":
    build()
