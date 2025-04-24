from setuptools import setup
import os
import stat

# Paths to include
SCRIPT_SRC = os.path.join('susops', 'susops.sh')
LOGO_FILES = [os.path.join('images', f) for f in os.listdir('images') if os.path.isfile(os.path.join('images', f))]

# Ensure the shell script is executable
st = os.stat(SCRIPT_SRC)
os.chmod(SCRIPT_SRC, st.st_mode | stat.S_IEXEC)

APP = ['susops-toolbar.py']
DATA_FILES = [
    # Bundle the shell script under Contents/Resources/scripts/
    ('susops', [SCRIPT_SRC]),
    # Bundle all logo assets under Contents/Resources/images/
    ('images', LOGO_FILES),
]

OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
    },
    'packages': ['rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
