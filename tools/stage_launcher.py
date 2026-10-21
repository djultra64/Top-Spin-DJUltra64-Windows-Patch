"""Stage only our launcher sources; never reset game configuration. djultra64."""
from pathlib import Path
import argparse
import shutil

SOURCE=Path(__file__).resolve().parent.parent

def stage(destination: Path):
    destination=destination.resolve()
    if not (destination/'TopSpin.exe').is_file():
        raise ValueError('Choose an existing extracted game folder.')
    package=destination/'launcher';package.mkdir(exist_ok=True)
    for path in (SOURCE/'launcher').glob('*.py'):shutil.copy2(path,package/path.name)
    helper=destination/'tools';helper.mkdir(exist_ok=True)
    for name in ['pml.py','controller_config.py','windows_graphics.py']:
        shutil.copy2(SOURCE/'tools'/name,helper/name)
    (helper/'__init__.py').touch(exist_ok=True)
    for name in ['TopSpinLauncher.sh','TopSpinLauncher.cmd','Play-TopSpin.sh','Play-TopSpin.cmd']:
        shutil.copy2(SOURCE/'portable'/name,destination/name)
    shutil.copy2(SOURCE/'launcher/README.md',destination/'Launcher-Readme.md')
    (destination/'TopSpinLauncher.sh').chmod(0o755)
    (destination/'Play-TopSpin.sh').chmod(0o755)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    print(stage(parser.parse_args().destination))
