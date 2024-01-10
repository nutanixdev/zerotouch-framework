import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["scrypt"], "excludes": [], "include_files": ['config/']}
# GUI applications require a different base on Windows (the default is for a
# console application).
base = None

if sys.platform == "win32":
    base = "Win32GUI"
setup(name="ztf",
      version="1.2.1",
      description="ZTF!",
      options={"build_exe": build_exe_options},
      executables=[Executable("main.py", base=base)])
