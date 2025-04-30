import os
import stat

from setuptools import setup

from version import VERSION

# ------------------- resource paths -------------------
ICON_FILE = os.path.join("images", "iconset", "susops.icns")
ICON_FOLDER = os.path.join("images", "iconset", "susops.iconset")
SCRIPT_SRC = os.path.join("susops-cli", "susops.sh")

# ------------------- make shell script executable -------------------
st = os.stat(SCRIPT_SRC)
os.chmod(SCRIPT_SRC, st.st_mode | stat.S_IEXEC)

# ------------------- py2app lists -------------------
DATA_FILES = [
    ("susops-cli", [SCRIPT_SRC]),
    *[(root, [os.path.join(root, f) for f in files])
      for root, dirs, files in os.walk(os.path.join("images", "icons"))],
    (os.path.join("images", "status"), [os.path.join("images", "status", f) for f in os.listdir(os.path.join("images", "status")) if os.path.isfile(os.path.join("images", "status", f))]),
    (os.path.join("images", "iconset"), [ICON_FILE, ICON_FOLDER]),
    "version.py"
]

OPTIONS = {
    "argv_emulation": True,
    "iconfile": ICON_FILE,
    "plist": {
        "CFBundleName": "SusOps",
        "CFBundleDisplayName": "SusOps",
        "CFBundleExecutable": "app.py",
        "LSUIElement": True,  # menu‑bar only, no dock icon
        "CFBundleIconFile": "susops",
    },
    "packages": ["rumps"],
}

setup(
    name="SusOps",
    version=VERSION,
    author="Manuel Schmid",
    url="https://github.com/mashb1t/susops-mac",
    app=["app.py"],
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
