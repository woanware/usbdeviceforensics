import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {"packages": ["Registry"]}

setup(  name = "usbdeviceforensics",
        version = "0.0.3",
        description = "usbdeviceforensics",
        options = {"build_exe": build_exe_options},
        executables = [Executable("usbdeviceforensics.py")])
