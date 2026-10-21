"""Rebuild a local game tree from the version-locked supplied media layout. Author: djultra64."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from tools.msi_reader import read_tables, file_layout, safe_name

KNOWN_SOURCE_VARIANTS = {
    'TopSpin.exe': '0bb3090d37956daa625faf917854c84f0263f4472c9235abf1f4c0d68721fe79',
    'OnlinePart(R).dll': '8e71dde8fe3db8c323c9e4426346f1324688b43ed562449220367c5117e40680',
}

def digest(path, kind='sha256'):
    h = hashlib.new(kind)
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def build(source: Path, destination: Path) -> dict:
    source, destination = source.resolve(), destination.resolve()
    if destination.exists():
        raise ValueError('Destination already exists; choose a fresh directory')
    tables = read_tables(source / 'TopSpin.msi')
    files = file_layout(tables)
    targets = [str(f['target']).lower() for f in files]
    if len(set(targets)) != len(targets):
        raise ValueError('MSI output path collision')
    hashes = {h['id']: struct.pack('<IIII', *(h[k] & 0xffffffff for k in ['h1','h2','h3','h4'])).hex()
              for h in tables['MsiFileHash']}
    media = sorted(tables['Media'], key=lambda m: m['last'])
    with tempfile.TemporaryDirectory(prefix='topspin-cabs-') as temp:
        cabinets = {}
        for m in media:
            if not m['cabinet']:
                continue
            name = safe_name(m['cabinet'])
            cabinet = source / name
            if not cabinet.is_file():
                raise FileNotFoundError(f'Missing cabinet: {cabinet}')
            unpack = Path(temp) / name
            unpack.mkdir()
            subprocess.run(['cabextract', '-q', '-d', str(unpack), str(cabinet)], check=True)
            cabinets[m['disk']] = {f.name.lower(): f for f in unpack.rglob('*') if f.is_file()}
        staged = Path(temp) / 'game'
        staged.mkdir()
        manifest = {'author': 'djultra64', 'status': 'extracted-unvalidated', 'files': [], 'source': []}
        for f in files:
            disk = next(m for m in media if f['sequence'] <= m['last'])
            if disk['cabinet']:
                original = cabinets[disk['disk']].get(f['id'].lower())
            else:
                original = source / 'program files/Atari/TopSpin' / f['target']
            if original is None or not original.is_file():
                raise FileNotFoundError(f'Missing source for {f["target"]}')
            if original.stat().st_size != f['size']:
                raise ValueError(f'Invalid size for {f["target"]}')
            matches_msi = f['id'] not in hashes or digest(original, 'md5') == hashes[f['id']]
            if not matches_msi and digest(original) != KNOWN_SOURCE_VARIANTS.get(str(f['target'])):
                raise ValueError(f'MSI hash mismatch for {f["target"]}')
            output = staged / f['target']
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, output)
            manifest['files'].append({'path': str(f['target']), 'size': f['size'],
                                      'sha256': digest(output), 'msi_md5': hashes.get(f['id']),
                                      'matches_msi': matches_msi})
        for name in ['TopSpin.msi'] + [m['cabinet'] for m in media if m['cabinet']]:
            original = source / name
            manifest['source'].append({'path': name, 'size': original.stat().st_size, 'sha256': digest(original)})
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, destination)
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('TopSpin'))
    parser.add_argument('--destination', type=Path, default=Path('dist/TopSpin-Portable'))
    args = parser.parse_args()
    result = build(args.source, args.destination)
    Path('reports/source-inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Extracted and verified {len(result["files"])} files into {args.destination}')
