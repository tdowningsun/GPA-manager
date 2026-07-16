# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onefile spec for the GPA Manager GUI.

Build with::

    pyinstaller --clean gpamanager.spec

Produces a single ``GPA Manager.exe`` plus the external ``config/``
folder next to it::

    dist/
     ├── GPA Manager.exe
     └── config/
          ├── gpa_scale.json
          ├── GPA_Rules_Guide_English.txt
          └── GPA_Rules_Guide_Traditional_Chinese.txt

Everything else (Python runtime, Tk, the ``GPA_Manager.ico`` icon)
is packed inside ``GPA Manager.exe`` and unpacked at runtime into
a temp directory exposed via ``sys._MEIPASS``. The runtime helper
:func:`data.get_internal_path` reads the icon out of that temp dir,
so the bundled-resource code path is identical to the onedir case
that the previous version of this spec produced.

The ``config/`` folder is intentionally NOT bundled. It ships as a
user-visible external sibling so:

* ``gpa_scale.json`` can be edited in place, and
* both ``GPA_Rules_Guide_*.txt`` guides sit visibly next to the EXE.

The post-build block at the bottom of this spec copies the source
``config/`` directory (next to the spec file) into ``dist/config/``;
:func:`data.get_resource_path` then resolves ``config/...`` against
``sys.executable``'s parent - which is ``dist/`` - so the runtime
finds the files at the path it expects.

Only ``gui.py`` is bundled here; the standalone CLI in ``main.py``
has its own (future) spec / distribution.
"""

block_cipher = None


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    # ``GPA_Manager.ico`` bundles into the EXE payload; at runtime
    # PyInstaller unpacks it into the temp dir exposed via
    # ``sys._MEIPASS`` and :func:`data.get_internal_path` reads it
    # back from there. The EXE icon is wired separately via the
    # ``icon=`` argument on the ``EXE`` block below. ``config/``
    # ships externally; see the post-build copy at the bottom of
    # this file.
    datas=[('GPA_Manager.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,   # onefile: pack native deps into the EXE
    a.datas,      # onefile: pack data files (the .ico) into the EXE
    a.zipfiles,   # onefile: pack any zip-imports into the EXE
    [],
    name='GPA Manager',
    # Embed the .ico into the EXE itself so File Explorer shows
    # the custom icon. The same file is also bundled into the
    # onefile payload (via the ``datas=`` entry above) so the Tk
    # window + taskbar can pick it up at runtime through
    # ``sys._MEIPASS``.
    icon='GPA_Manager.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed application; no console window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)


# ---------------------------------------------------------------------------
# Post-build: copy the external ``config/`` folder next to the EXE.
#
# PyInstaller onefile mode writes the EXE at ``dist/GPA Manager.exe``.
# We copy the entire source ``config/`` folder (next to this spec
# file) into ``dist/config/`` so every file the runtime expects -
# the JSON scale plus both language guides - ends up next to the
# EXE in the final release. ``data.get_resource_path`` then resolves
# ``config/...`` against the EXE's parent directory, so this
# external copy is exactly what the EXE reads from at runtime.
#
# The whole folder is copied (rather than individual files) so
# future additions to ``config/`` (more languages, additional
# reference docs, ...) ship automatically without touching the spec.
# ---------------------------------------------------------------------------
import os
import shutil


# Files the release must include under ``config/``. The runtime
# already tracks this list in ``data.EXPECTED_CONFIG_FILES``; we
# duplicate it here as a release-side sanity check so a missing
# file is caught at packaging time instead of only at runtime.
EXPECTED_CONFIG_FILES = (
    "gpa_scale.json",
    "GPA_Rules_Guide_English.txt",
    "GPA_Rules_Guide_Traditional_Chinese.txt",
)


src_config = os.path.join(SPECPATH, 'config')
dst_config = os.path.join('dist', 'config')

if os.path.isdir(src_config):
    present = {
        name for name in os.listdir(src_config)
        if os.path.isfile(os.path.join(src_config, name))
    }
    missing = [n for n in EXPECTED_CONFIG_FILES if n not in present]
    if missing:
        print(
            f"[gpamanager.spec] WARNING: source config/ is missing: "
            f"{', '.join(missing)}; the release will be incomplete."
        )
    if os.path.exists(dst_config):
        shutil.rmtree(dst_config)
    shutil.copytree(src_config, dst_config)
    print(f"[gpamanager.spec] copied {src_config} -> {dst_config}")
else:
    print(
        f"[gpamanager.spec] WARNING: {src_config} not found; the "
        f"release will be missing gpa_scale.json and the language guides."
    )