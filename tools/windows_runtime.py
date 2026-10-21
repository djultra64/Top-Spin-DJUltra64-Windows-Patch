"""Build a private, frozen Windows launcher on Windows. Own work: djultra64.

PyInstaller includes CPython and Tcl/Tk; no game assets enter this build.
https://pyinstaller.org/en/stable/usage.html
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

PYINSTALLER_VERSION = '6.22.3'
SOURCE = Path(__file__).resolve().parent.parent


def pyinstaller_command(python: Path, source: Path, work: Path) -> list[str]:
    return [str(python), '-m', 'PyInstaller', '--clean', '--noconfirm', '--onedir',
            '--windowed', '--noupx', '--name', 'TopSpinLauncher',
            '--contents-directory', 'runtime-windows-launcher',
            '--paths', str(source), '--distpath', str(work/'dist'),
            '--workpath', str(work/'work'), '--specpath', str(work/'spec'),
            str(source/'native/launcher/windows_entry.py')]


def validate_bundle(bundle: Path):
    runtime = bundle/'runtime-windows-launcher'
    if not (bundle/'TopSpinLauncher.exe').is_file() or not runtime.is_dir():
        raise ValueError('The Windows launcher runtime is incomplete.')
    if not list(runtime.glob('python3*.dll')) or not (runtime/'_tkinter.pyd').is_file():
        raise ValueError('The Windows launcher runtime is missing CPython or Tk.')
    # Official Tcl/Tk 9 Windows DLLs embed their script archives. Older builds
    # need the script directories collected by the PyInstaller Tk hook.
    embedded_tcl9=all((runtime/name).is_file() for name in ['tcl90.dll','tcl9tk90.dll'])
    if not embedded_tcl9:
        for relative in ['_tcl_data/init.tcl', '_tk_data/tk.tcl']:
            if not (runtime/relative).is_file():
                raise ValueError('The Windows launcher runtime is missing Tcl/Tk scripts.')


def stage_bundle(bundle: Path, destination: Path):
    validate_bundle(bundle)
    executable = destination/'TopSpinLauncher.exe'
    direct = destination/'Play-TopSpin.exe'
    runtime = destination/'runtime-windows-launcher'
    if executable.exists() or direct.exists() or runtime.exists():
        raise FileExistsError('The destination already contains a Windows launcher; choose a fresh staging folder.')
    runtime.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle/'runtime-windows-launcher', runtime)
    try:
        shutil.copy2(bundle/'TopSpinLauncher.exe', executable)
        if (bundle/'Play-TopSpin.exe').is_file():
            shutil.copy2(bundle/'Play-TopSpin.exe', direct)
    except Exception:
        shutil.rmtree(runtime)
        executable.unlink(missing_ok=True)
        direct.unlink(missing_ok=True)
        raise
    notices = bundle/'licenses/windows-launcher'
    if notices.exists():
        shutil.copytree(notices, destination/'licenses/windows-launcher', dirs_exist_ok=True)
    manifest = bundle/'windows-launcher-build.json'
    if manifest.exists():
        (destination/'.portable').mkdir(exist_ok=True)
        shutil.copy2(manifest, destination/'.portable/windows-launcher-build.json')


def build(work: Path) -> Path:
    if os.name != 'nt':
        raise ValueError('Build the frozen Windows launcher on Windows, using CPython with Tcl/Tk.')
    if importlib.metadata.version('pyinstaller') != PYINSTALLER_VERSION:
        raise ValueError('Install pyinstaller==' + PYINSTALLER_VERSION + ' in the private build environment.')
    import tkinter
    # Check the actual interpreter includes Tcl/Tk before running the freezer.
    interpreter = tkinter.Tcl()
    interpreter.eval('info patchlevel')
    work = work.resolve(); work.mkdir(parents=True, exist_ok=True)
    output = work/'dist/TopSpinLauncher'
    if output.exists():
        raise FileExistsError('Choose a fresh build directory; an earlier launcher build already exists.')
    subprocess.run(pyinstaller_command(Path(sys.executable), SOURCE, work), check=True, cwd=SOURCE)
    from tools.windows_direct import build_direct_entry
    build_direct_entry(output)
    validate_bundle(output)
    notices = output/'licenses/windows-launcher'; notices.mkdir(parents=True, exist_ok=True)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.is_file():
        raise ValueError('CPython license was not found; retain the official Python distribution notices.')
    shutil.copy2(python_license, notices/'CPython-LICENSE.txt')
    import PyInstaller
    pyinstaller_license = Path(PyInstaller.__file__).parent/'COPYING.txt'
    if not pyinstaller_license.is_file():
        # Wheels keep the license in distribution metadata instead.
        distribution = importlib.metadata.distribution('pyinstaller')
        candidates = [distribution.locate_file(path) for path in distribution.files
                      if str(path).replace('\\', '/').endswith('/COPYING.txt')]
        if not candidates:
            raise ValueError('PyInstaller license was not found.')
        pyinstaller_license = candidates[0]
    shutil.copy2(pyinstaller_license, notices/'PyInstaller-COPYING.txt')
    # Tcl/Tk 9 embeds scripts/notices inside its DLLs. Retain separate readable
    # copies from the official CPython distribution archives as well.
    for archive in (Path(sys.base_prefix)/'tcl').glob('*.zip'):
        with zipfile.ZipFile(archive) as package:
            for member in package.namelist():
                if member.endswith('/license.terms'):
                    label=member.split('/')[0]
                    (notices/(label+'-license.terms')).write_bytes(package.read(member))
    for directory in (Path(sys.base_prefix)/'tcl').glob('*'):
        if directory.is_dir():
            for name in ['license.terms','license','LICENSE']:
                if (directory/name).is_file():
                    shutil.copy2(directory/name,notices/(directory.name+'-'+name))
    files = {str(path.relative_to(output)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob('*')) if path.is_file()}
    manifest = {'author': 'djultra64', 'python': sys.version, 'pyinstaller': PYINSTALLER_VERSION,
                'platform': sys.platform, 'files_sha256': files}
    (output/'windows-launcher-build.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--stage', type=Path)
    args = parser.parse_args()
    bundle = build(args.work)
    if args.stage:
        stage_bundle(bundle, args.stage)
    print(bundle)


if __name__ == '__main__':
    main()
