"""Verify immutable extracted assets and the declared patched binary. djultra64."""
from pathlib import Path
import argparse
import json
from tools.build_portable import digest
from launcher.integrity import MANIFEST, checked_path, verify_integrity

def verify(destination: Path, inventory: Path | None = None):
    destination=Path(destination).resolve()
    if checked_path(destination,MANIFEST).exists():
        result=verify_integrity(destination)
        if not result.ok:
            raise ValueError('\n'.join([result.summary]+
                [f'Missing: {name}' for name in result.missing]+
                [f'SHA256 mismatch: {name}' for name in result.modified]))
        return result.checked
    if inventory is None:
        raise ValueError('No integrity manifest or source inventory was supplied')
    source=json.loads(inventory.read_text())
    patched=json.loads((destination/'portable-build.json').read_text())
    failures=[]
    for item in source['files']:
        name=item['path']
        path=checked_path(destination,name)
        if not path.is_file():
            failures.append(f'Missing: {name}')
            continue
        if name=='Config.pml':
            continue  # User settings are intentionally mutable.
        expected=patched['patched_sha256'] if name=='TopSpin.exe' else item['sha256']
        if digest(path)!=expected:
            failures.append(f'SHA256 mismatch: {name}')
    if failures:
        raise ValueError('\n'.join(failures))
    return len(source['files'])-1

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--destination',type=Path,default=Path('dist/TopSpin-Portable'))
    p.add_argument('--inventory',type=Path,default=Path('reports/source-inventory.json'))
    a=p.parse_args()
    print(f'Verified {verify(a.destination,a.inventory)} immutable files')
