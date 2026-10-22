"""Rebuild a local game tree from the version-locked supplied media layout. Author: djultra64."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import os
import stat
import time
import ctypes
import errno
import sys
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

def validate_cabinet(path: Path, expected: dict) -> set:
    """Validate every CAB output name before allowing cabextract to write files.

    Only flat, MSI-declared file identifiers are accepted. No cabinet chain,
    alternate paths, unlisted extra entries or ambiguous case aliases can reach
    the extractor. The reader never decompresses or executes cabinet contents.
    """
    size=path.stat().st_size
    if not 36<=size<=2**31:raise ValueError('Unsupported cabinet size')
    wanted={name.casefold():length for name,length in expected.items()}
    if len(wanted)!=len(expected):raise ValueError('Duplicate cabinet identifiers')
    found=set()
    with path.open('rb') as stream:
        header=stream.read(36)
        declared=struct.unpack_from('<I',header,8)[0]
        offset=struct.unpack_from('<I',header,16)[0]
        count,flags=struct.unpack_from('<HH',header,28)
        if (header[:4]!=b'MSCF' or declared!=size or flags&3 or flags&~7
                or not 36<=offset<size or count>100000):
            raise ValueError('Unsupported cabinet header or cabinet chain')
        stream.seek(offset)
        for _ in range(count):
            row=stream.read(16)
            if len(row)!=16:raise ValueError('Truncated cabinet file table')
            length=struct.unpack_from('<I',row)[0];raw=bytearray()
            for _ in range(256):
                value=stream.read(1)
                if value==b'\0':break
                if not value:raise ValueError('Truncated cabinet filename')
                raw.extend(value)
            else:raise ValueError('Excessive cabinet filename length')
            try:name=raw.decode('ascii')
            except UnicodeError:raise ValueError('Unsupported cabinet identifier encoding') from None
            if safe_name(name)!=name:raise ValueError('Unsafe cabinet identifier')
            key=name.casefold()
            if key in found or key not in wanted or wanted[key]!=length:
                raise ValueError('Unexpected cabinet identifier, duplicate or file size')
            found.add(key)
        if found!=set(wanted):raise ValueError('Cabinet does not contain the declared MSI files')
    return found


def media_layout(tables, files):
    media=sorted(tables['Media'],key=lambda row:row['last'] or -1)
    if (not media or len(media)>1000 or len({m['disk'] for m in media})!=len(media)
            or any(type(m['disk']) is not int or m['disk']<=0 or type(m['last']) is not int
                   or m['last']<=0 or m.get('source') for m in media)
            or any(a['last']>=b['last'] for a,b in zip(media,media[1:]))
            or any(f['sequence']>media[-1]['last'] for f in files)):
        raise ValueError('Unsupported MSI media layout')
    for row in media:
        name=row['cabinet']
        if name and (name.startswith('#') or safe_name(name)!=name):
            raise ValueError('Unsupported or unsafe MSI cabinet name')
    cabinets=[m['cabinet'].casefold() for m in media if m['cabinet']]
    if len(cabinets)!=len(set(cabinets)):raise ValueError('Duplicate MSI cabinet names')
    return media


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():raise InterruptedError('Installation cancelled.')


def publish_noreplace(staged: Path,destination: Path):
    """Publish a fresh tree without replacing a racing empty destination.

    Linux publication is atomic. Other platforms exclusively reserve the
    output directory before copying, retaining the source until copy success.
    """
    if sys.platform=='linux':
        libc=ctypes.CDLL(None,use_errno=True)
        rename=getattr(libc,'renameat2',None)
        if rename is None:raise OSError('Atomic non-overwriting directory publication is unavailable.')
        rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        rename.restype=ctypes.c_int
        if rename(-100,os.fsencode(staged),-100,os.fsencode(destination),1):
            number=ctypes.get_errno()
            if number==errno.EEXIST:raise FileExistsError('Destination appeared during installation; it was preserved.')
            raise OSError(number,os.strerror(number),str(destination))
        return
    destination.mkdir()  # Exclusive reservation; existing directories survive.
    try:shutil.copytree(staged,destination,dirs_exist_ok=True)
    except BaseException:
        shutil.rmtree(destination)
        raise
    shutil.rmtree(staged)


def _extract_cabinet(command,cancel):
    # The owned extraction process can be stopped on cancellation; no game or
    # existing client process is touched. Discard untrusted tool diagnostics.
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
        try:
            deadline=time.monotonic()+300
            while True:
                _check_cancel(cancel)
                if time.monotonic()>deadline:raise TimeoutError('Cabinet extraction timed out.')
                try:
                    code=process.wait(timeout=0.2);break
                except subprocess.TimeoutExpired:pass
            if code:raise ValueError('Cabinet extraction failed; no game was installed.')
        except BaseException:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            raise


def build(source: Path, destination: Path, *, cabextract=None, progress=None, cancel=None) -> dict:
    source, destination = source.resolve(), destination.absolute()
    if os.path.lexists(destination):
        raise ValueError('Destination already exists; choose a fresh directory')
    tables = read_tables(source / 'TopSpin.msi')
    files = file_layout(tables)
    targets = [str(f['target']).lower() for f in files]
    if len(set(targets)) != len(targets):
        raise ValueError('MSI output path collision')
    hashes = {h['id']: struct.pack('<IIII', *(h[k] & 0xffffffff for k in ['h1','h2','h3','h4'])).hex()
              for h in tables['MsiFileHash']}
    media = media_layout(tables,files)
    destination.parent.mkdir(parents=True,exist_ok=True)
    _check_cancel(cancel)
    # Keep large cabinet/game staging on the selected destination filesystem.
    with tempfile.TemporaryDirectory(prefix='.topspin-cabs-',dir=destination.parent) as temp:
        cabinets = {}
        for m in media:
            if not m['cabinet']:
                continue
            name = safe_name(m['cabinet'])
            cabinet = source / name
            if not cabinet.is_file():
                raise FileNotFoundError(f'Missing cabinet: {cabinet}')
            expected={f['id']:f['size'] for f in files
                      if next(row for row in media if f['sequence']<=row['last'])['disk']==m['disk']}
            validate_cabinet(cabinet,expected)
            _check_cancel(cancel)
            if progress:progress('Extracting cabinet '+name+'...')
            unpack = Path(temp) / name
            unpack.mkdir()
            _extract_cabinet([str(cabextract or 'cabextract'),'-q','-d',str(unpack),str(cabinet)],cancel)
            extracted={}
            for entry in unpack.iterdir():
                if not stat.S_ISREG(entry.lstat().st_mode) or entry.name.casefold() not in {n.casefold() for n in expected}:
                    raise ValueError('Cabinet extraction produced an unexpected file or link')
                extracted[entry.name.casefold()]=entry
            if len(extracted)!=len(expected):raise ValueError('Cabinet extraction is incomplete')
            cabinets[m['disk']] = extracted
        staged = Path(temp) / 'game'
        staged.mkdir()
        manifest = {'author': 'djultra64', 'status': 'extracted-unvalidated', 'files': [], 'source': []}
        for f in files:
            _check_cancel(cancel)
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
        _check_cancel(cancel)
        # No second complete game copy: the sibling staging directory shares
        # the destination filesystem and can be renamed after verification.
        publish_noreplace(staged,destination)
    return manifest

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('TopSpin'))
    parser.add_argument('--destination', type=Path, default=Path('dist/TopSpin-Portable'))
    args = parser.parse_args()
    result = build(args.source, args.destination)
    Path('reports/source-inventory.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Extracted and verified {len(result["files"])} files into {args.destination}')
