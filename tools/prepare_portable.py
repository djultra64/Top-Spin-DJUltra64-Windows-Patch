"""Apply reproducible development settings to an extracted game. djultra64."""
from pathlib import Path
import argparse
import json
import hashlib
import shutil
import subprocess
from tools.patch_game import patch_executable
from tools.pml import Pml
from tools.stage_launcher import stage as stage_launcher

def make_config(original: bytes, width: int, height: int) -> bytes:
    # RefreshRate also selects the PAL animation banks. The supplied WAD has
    # Player50/PlayerW50, and no Player/PlayerW NTSC banks. Preserve that base.
    config=Pml(original)
    for section, key, value in [
        ('Video','FullScreen','true'), ('Video','Res_X',str(width)),
        ('Video','Res_Y',str(height)), ('Video','RefreshRate','50'),
        ('General','Language','Eng'), ('General','LaunchPart','e_TopSpin_MenuPart'),
        ('DebugSettings','AutoSynchronize','true'), ('DebugSettings','ShowFPS','false')]:
        config.set(section,key,value)
    return config.encode()

def prepare(source: Path, destination: Path, width: int, height: int):
    if width < 640 or height < 480 or width * 9 != height * 16:
        raise ValueError('Choose a 16:9 resolution, at least 640x480')
    Path('build').mkdir(exist_ok=True)
    for name in ['portable-path', 'portable-save-drives', 'portable-options-delete']:
        subprocess.run(['as', '--32', f'patches/{name}.s', '-o', f'build/{name}.o'], check=True)
        subprocess.run(['objcopy', '-O', 'binary', '-j', '.text',
                        f'build/{name}.o', f'build/{name}.bin'], check=True)
    raw=(source/'program files/Atari/TopSpin/TopSpin.exe').read_bytes()
    stub=Path('build/portable-path.bin').read_bytes()
    patched=patch_executable(
        raw, stub, width/height, fix_options_save=True, fix_career_storage=True,
        fix_creator_camera_input=True,
        save_paths_stub=Path('build/portable-save-drives.bin').read_bytes(),
        delete_options_stub=Path('build/portable-options-delete.bin').read_bytes())
    (destination/'TopSpin.exe').write_bytes(patched)
    for folder in ['T', 'U']:
        (destination/folder).mkdir(exist_ok=True)
    (destination/'Config.pml').write_bytes(make_config((source/'program files/Atari/TopSpin/Config.pml').read_bytes(),width,height))
    for name in ['Play-TopSpin.sh','Play-TopSpin.cmd']:
        shutil.copy2(Path('portable')/name,destination/name)
    stage_launcher(destination)
    manifest={'author':'djultra64','status':'development-not-release',
              'original_sha256':hashlib.sha256(raw).hexdigest(),
              'patched_sha256':hashlib.sha256(patched).hexdigest(),
              'resolution':[width,height],
              'patches':['module-directory lookup','camera default aspect ratio',
                         'options and career real free-space queries',
                         'creator camera update without active input',
                         'portable T/U save paths and matching options deletion'],
              'timing':'PAL 50; AutoSynchronize=true; external frame generation runtime remains in development'}
    (destination/'portable-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,default=Path('TopSpin'))
    p.add_argument('--destination',type=Path,default=Path('dist/TopSpin-Portable'))
    p.add_argument('--width',type=int,default=1920)
    p.add_argument('--height',type=int,default=1080)
    args=p.parse_args()
    prepare(args.source,args.destination,args.width,args.height)
