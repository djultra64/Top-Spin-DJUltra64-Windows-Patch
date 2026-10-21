"""Version-locked local main-menu delta; no original game assets. djultra64."""
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import zipfile
from tools.glyph_install import _replace

SOURCE_SHA256='b1a7c37765fd8067db97adbf9a653147b82e1aeaa2e957ff6c3bbdd451d704e3'
MEMBER_SHA256={
 'Scenes/newmain.scene':'7ceece1730c09fb0b3007d6d0eee5610fb1cca015f09b8d648ccabb317d7be00',
 'Scenes/newmain.sceneData':'fc0464ecb5d1bfa58e7184c46739aa9d61bbbd4b2b12c10fa1cae4d44bdd08d4',
}
ANIMATION_SHA256='9c0f37a928e8f429dc4a97277f777b2f8db2de565c78feb9b43a63f5adfc2239'
RECIPE=Path(__file__).with_suffix('.lua')


def patch_main_menu(raw:bytes,lua:Path)->bytes:
    """Patch exactly the vetted main menu, using a compatible local Lua 5.0.3.

    Calling twice or passing another game version is intentionally rejected.
    No destination is written until both chunks have compiled and reloaded.
    """
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Unsupported MainMenu.rui; exact original media is required.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        inputs={}
        for name,expected in MEMBER_SHA256.items():
            if archive.namelist().count(name)!=1:raise ValueError('Unexpected main menu member count.')
            data=archive.read(name)
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Unsupported main menu chunk.')
            inputs[name]=data
    with tempfile.TemporaryDirectory(prefix='topspin-quit-') as folder:
        root=Path(folder)
        for name,data in inputs.items():(root/Path(name).name).write_bytes(data)
        output_data=root/'quit.sceneData';output_events=root/'quit.scene'
        result=subprocess.run([str(Path(lua).resolve()),str(RECIPE.resolve()),
                               str(root/'newmain.sceneData'),str(root/'newmain.scene'),
                               str(output_data),str(output_events),str(root/'original-animation.bin')],capture_output=True,text=True,timeout=30)
        if result.returncode or 'QUIT_MENU_COMPILED_AND_RELOADED' not in result.stdout:
            raise ValueError('Main menu recipe failed: '+result.stderr.strip())
        if hashlib.sha256((root/'original-animation.bin').read_bytes()).hexdigest()!=ANIMATION_SHA256:
            raise ValueError('Unsupported main menu animation blob.')
        outputs={'Scenes/newmain.sceneData':output_data.read_bytes(),'Scenes/newmain.scene':output_events.read_bytes()}
    for name,payload in outputs.items():
        original=inputs[name]
        if original.startswith(b'\x1bLua') and payload[:14]!=original[:14]:
            raise ValueError('Lua compiler header does not match the game bytecode format.')
        raw=_replace(raw,name,payload)
    return raw


def patch_file(source:Path,destination:Path,lua:Path)->str:
    if source.resolve()==destination.resolve():raise ValueError('Use a separate private output path.')
    changed=patch_main_menu(source.read_bytes(),lua)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(changed)
    return hashlib.sha256(changed).hexdigest()


def main():
    parser=argparse.ArgumentParser(description='Add the version-checked Quit Game menu row to a private copy.')
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--lua',type=Path,required=True)
    arguments=parser.parse_args()
    print(patch_file(arguments.source,arguments.destination,arguments.lua))

if __name__=='__main__':main()
