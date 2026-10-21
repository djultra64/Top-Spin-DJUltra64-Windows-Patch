"""Create a PRIVATE local portable game folder from an assembled candidate.

Contains user-owned original game files and may retain the user's CD key inside
Config.pml. Never publish its output. Public patches are a separate deliverable.
Author: djultra64.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import tempfile
from launcher.integrity import build_manifest, checked_path, relative_path, write_manifest

ROOT_EXTRAS = ('TopSpinLauncher.exe','TopSpinLauncher.sh','TopSpinLauncher.cmd',
               'Play-TopSpin.exe','Play-TopSpin.sh','Play-TopSpin.cmd','Launcher-Readme.md','dxvk.conf',
               'd3d8.dll','d3d9.dll','dgVoodoo.conf')
EXCLUDED_PARTS = {'__pycache__','.git','.cache','cache','caches','logs','log',
                  'prefix','proton-prefix','wineprefix','pfx','shadercache','.build-id'}
EXCLUDED_SUFFIXES = {'.pyc','.pyo','.log','.bak','.key','.dmp','.lock'}


def _runtime_file(name,root):
    path=relative_path(name)
    # Some official Python builds ship standard-library modules only as .pyc.
    # Those are runtime files, unlike __pycache__ or bytecode beside .py sources.
    sourceless=(path.parts[:2]==('runtime','python') and path.suffix=='.pyc' and
                not (root/path).with_suffix('.py').is_file())
    return (not any(part.lower() in EXCLUDED_PARTS for part in path.parts) and
            (path.suffix.lower() not in EXCLUDED_SUFFIXES or sourceless))

def _source_file(root,name):
    path=root/relative_path(name)
    if name.startswith('runtime/') and path.is_symlink():
        # Materialize bundled interpreter aliases, never host files or links in
        # the resulting ZIP. Directory links remain rejected by the tree walk.
        target=path.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('Runtime alias escapes the package source: '+name)
        return target
    return checked_path(root,name)


def _platform_file(name,platform):
    if platform=='windows':
        return not (name.startswith(('runtime/linux/','runtime/python/')) or
                    name=='.portable/runtime.json' or name.endswith('.sh'))
    if platform=='linux':
        return not (name.startswith(('runtime-windows-launcher/','runtime/windows/')) or
                    name in {'.portable/windows-graphics.json','TopSpinLauncher.exe','Play-TopSpin.exe','d3d8.dll','d3d9.dll','dgVoodoo.conf'} or
                    name.endswith('.cmd'))
    return True


def package_portable(source,destination,inventory,*,platform='combined'):
    """Copy inventory game files + own launcher/runtime, then checksum immutables.

    ``inventory`` accepts the decoded source-inventory dictionary or its JSON path.
    Existing destination folders are never modified. No archives are published.
    """
    if platform not in {'windows','linux','combined'}:raise ValueError('Unknown package platform')
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Destination already exists; choose a fresh folder')
    if destination.is_relative_to(source):raise ValueError('Destination must be outside the source folder')
    if not isinstance(inventory,dict):inventory=json.loads(Path(inventory).read_text())
    names=set()
    for item in inventory['files']:
        name=item['path'];relative_path(name)
        # Original inventory is authoritative for game resources, not personal state.
        if relative_path(name).parts[0].lower() in {'t','u','z','.portable'}:continue
        names.add(name)
    for name in ROOT_EXTRAS:
        if (source/name).exists():names.add(name)
    for folder in ('launcher','tools','runtime','runtime-windows-launcher','licenses','artwork/steam','.portable/glyphs'):
        base=source/folder
        if base.is_symlink():raise ValueError(f'Symbolic package directory: {folder}')
        if not base.exists():continue
        for current,dirs,files in os.walk(base,followlinks=False):
            for name in dirs:
                if (Path(current)/name).is_symlink():raise ValueError('Symbolic package directory')
            dirs[:]=[name for name in dirs if name.lower() not in EXCLUDED_PARTS]
            for filename in files:
                path=Path(current)/filename;name=path.relative_to(source).as_posix()
                if _runtime_file(name,source):names.add(name)
    for name in ('.portable/input.json','.portable/runtime.json','.portable/windows-graphics.json'):
        if (source/name).exists():names.add(name)
    names={name for name in names if _platform_file(name,platform)}
    folded={}
    for name in names:
        if name.casefold() in folded:raise ValueError(f'Windows path collision: {name}')
        folded[name.casefold()]=name
        path=_source_file(source,name)
        if not path.is_file():raise FileNotFoundError(f'Missing package file: {name}')
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=f'.{destination.name}-',dir=destination.parent))
    try:
        for name in sorted(names):
            output=staging/name;output.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(_source_file(source,name),output)
        # These replace original virtual save volumes. The game expects their
        # roots to exist before creating options/profile files within them.
        for name in ['T','U']:(staging/name).mkdir(exist_ok=True)
        manifest=build_manifest(staging,names)
        write_manifest(staging,manifest)
        report={'version':1,'author':'djultra64','kind':'private-local-game-package',
                'warning':'Contains user-owned game files. Do not publish or share this folder.',
                'platform':platform,'files':len(names),'immutable_files':len(manifest['files'])}
        (staging/'.portable/package.json').write_text(json.dumps(report,indent=2)+'\n')
        staging.rename(destination)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--inventory',type=Path,default=Path('reports/source-inventory.json'))
    parser.add_argument('--platform',choices=['windows','linux','combined'],default='combined')
    args=parser.parse_args()
    print(json.dumps(package_portable(args.source,args.destination,args.inventory,platform=args.platform),indent=2))
