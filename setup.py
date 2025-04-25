import os
import stat

from setuptools import setup

# ------------------- resource paths -------------------
SCRIPT_SRC = os.path.join('susops-cli', 'susops.sh')
LOGO_FILES = [os.path.join('images', f) for f in os.listdir('images') if os.path.isfile(os.path.join('images', f))]

ICON_FILE = os.path.join('images', 'susops.icns')

# ------------------- make shell script executable -------------------
st = os.stat(SCRIPT_SRC)
os.chmod(SCRIPT_SRC, st.st_mode | stat.S_IEXEC)

# ------------------- py2app lists -------------------
DATA_FILES = [
    ('susops-cli', [SCRIPT_SRC]),
    ('images', LOGO_FILES + [ICON_FILE]),
]

OPTIONS = {
    'argv_emulation': True,
    'iconfile': ICON_FILE,
    'plist': {
        'CFBundleName': 'SusOps',
        'CFBundleDisplayName': 'SusOps',
        'CFBundleExecutable': 'app.py',
        'LSUIElement': True,  # menu‑bar only, no dock icon
        'CFBundleIconFile': 'susops',
    },
    'packages': ['rumps'],
}

setup(
    name='SusOps',
    version='1.0.0',
    author='Manuel Schmid',
    url='https://github.com/mashb1t/susops-mac',
    app=["app.py"],
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
