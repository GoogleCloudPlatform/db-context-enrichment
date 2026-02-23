# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata, collect_all

def collect_dynamic_resources():
    datas = []
    binaries = []
    hiddenimports = []
    
    # 1. Project Assets
    # Include default prompts directory. Paths are relative to this spec file.
    datas.append(('prompts', 'prompts'))
    # Include README from the repo root (parent directory)
    datas.append(('../README.md', '.'))

    # 2. Dependency Metadata / Complex Packages
    # Google Auth often requires deep inspection
    tmp_ret = collect_all('google.auth')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
    
    # Copy metadata for packages that use entry points or version checks
    packages_needing_metadata = [
        'fastmcp', 
        'google-genai', 
        'mcp', 
        'toolbox-core',
    ]

    for pkg in packages_needing_metadata:
        try:
            datas += copy_metadata(pkg, recursive=True)
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to copy required metadata for {pkg}.")
            raise e

    return datas, binaries, hiddenimports

project_datas, project_binaries, project_hiddenimports = collect_dynamic_resources()

a = Analysis(
    ['main.py'],
    pathex=['.'], # Run in the current context (mcp folder)
    binaries=project_binaries,
    datas=project_datas,
    hiddenimports=project_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='db-context-enrichment',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
