"""Read the tables required for this MSI without executing its installer.

Top Spin's database uses 16-bit string references. MSI integers are stored
with the sign bit inverted; table columns are stored consecutively.
Own tooling: djultra64. Requires olefile.
"""
from pathlib import Path, PurePosixPath
import struct
import olefile

CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._'
SCHEMAS = {
    'File': [('id', 's'), ('component', 's'), ('name', 's'), ('size', 'i4'),
             ('version', 's'), ('language', 's'), ('attributes', 'i2'), ('sequence', 'i2')],
    'Directory': [('id', 's'), ('parent', 's'), ('name', 's')],
    'Component': [('id', 's'), ('guid', 's'), ('directory', 's'),
                  ('attributes', 'i2'), ('condition', 's'), ('keypath', 's')],
    'Media': [('disk', 'i2'), ('last', 'i2'), ('prompt', 's'),
              ('cabinet', 's'), ('label', 's'), ('source', 's')],
    'Registry': [('id', 's'), ('root', 'i2'), ('key', 's'), ('name', 's'),
                 ('value', 's'), ('component', 's')],
    'MsiFileHash': [('id', 's'), ('options', 'i2'), ('h1', 'i4'),
                    ('h2', 'i4'), ('h3', 'i4'), ('h4', 'i4')],
}

def stream_name(encoded):
    out = ''
    for c in encoded:
        n = ord(c)
        if n == 0x4840:
            out += '!'
        elif 0x3800 <= n < 0x4800:
            n -= 0x3800
            out += CHARS[n & 63] + CHARS[n >> 6]
        elif 0x4800 <= n < 0x4840:
            out += CHARS[n - 0x4800]
        else:
            out += c
    return out

def read_tables(path: Path) -> dict:
    with olefile.OleFileIO(path) as db:
        streams = {stream_name(p[0]): p for p in db.listdir() if len(p) == 1}
        pool = db.openstream(streams['!_StringPool']).read()
        data = db.openstream(streams['!_StringData']).read()
        codepage, flags = struct.unpack_from('<HH', pool)
        if flags & 0x8000:
            raise ValueError('Unsupported MSI with 24-bit string references')
        strings = ['']
        pos = 0
        for offset in range(4, len(pool), 4):
            length, refs = struct.unpack_from('<HH', pool, offset)
            strings.append(data[pos:pos + length].decode(f'cp{codepage or 1252}'))
            pos += length
        if pos != len(data):
            raise ValueError('Unexpected MSI string pool layout')
        tables = {}
        for name, schema in SCHEMAS.items():
            raw = db.openstream(streams['!' + name]).read()
            widths = [4 if t == 'i4' else 2 for _, t in schema]
            count, remainder = divmod(len(raw), sum(widths))
            if remainder:
                raise ValueError(f'Invalid {name} table length')
            rows = [{} for _ in range(count)]
            pos = 0
            for (column, kind), width in zip(schema, widths):
                for row in rows:
                    value = int.from_bytes(raw[pos:pos + width], 'little')
                    pos += width
                    row[column] = strings[value] if kind == 's' else (
                        value - (1 << (width * 8 - 1)) if value else None)
            tables[name] = rows
        return tables

def safe_name(value: str) -> str:
    if not isinstance(value,str):raise ValueError('MSI filenames must be text')
    if value.count('|')>1:raise ValueError('MSI filenames support at most one short|long alias pair')
    name = value.split('|')[-1]
    reserved={'con','prn','aux','nul'}|{f'{prefix}{i}' for prefix in ('com','lpt') for i in range(1,10)}
    if (not name or len(name)>255 or name in ('.', '..') or name.endswith((' ','.'))
            or name.split('.')[0].casefold() in reserved
            or any(ord(c)<32 or ord(c)==127 or c in '/\\:\x00<>"?*' for c in name)):
        raise ValueError(f'Unsafe MSI filename: {value!r}')
    return name

def file_layout(tables: dict) -> list:
    dirs = {d['id']: d for d in tables['Directory']}
    components = {c['id']: c for c in tables['Component']}
    files=tables['File']
    if (len(dirs)!=len(tables['Directory']) or len(components)!=len(tables['Component'])
            or len({f['id'].casefold() for f in files})!=len(files) or len(files)>100000):
        raise ValueError('Duplicate or excessive MSI identifiers')
    if (any(type(f['size']) is not int or not 0<=f['size']<=2**31
            or type(f['sequence']) is not int or f['sequence']<=0
            or safe_name(f['id'])!=f['id'] for f in files)
            or sum(f['size'] for f in files)>16*1024**3):
        raise ValueError('Invalid MSI file identifiers, sequences or size limits')
    # Source layout begins under the install directory, independent of ProgramFilesFolder.
    def ancestors(key):
        result=set()
        while key:
            if key in result or len(result)>=64:raise ValueError('Cyclic MSI directory tree')
            result.add(key);key=dirs[key]['parent']
        return result
    chains=[ancestors(components[f['component']]['directory']) for f in files]
    installs=[d['id'] for d in dirs.values()
              if d['name'].split(':')[0].split('|')[-1].lower() == 'topspin'
              and chains and all(d['id'] in chain for chain in chains)]
    if len(installs)!=1:raise ValueError('MSI must declare one TopSpin install directory')
    install=installs[0]
    def directory(key, seen=()):
        if key == install:
            return PurePosixPath('.')
        if key in seen or len(seen)>=64:
            raise ValueError('Cyclic MSI directory tree')
        row = dirs[key]
        if not row['parent']:
            raise ValueError(f'File outside game directory: {key}')
        name = row['name'].split(':')[-1]
        parent = directory(row['parent'], seen + (key,))
        return parent if name == '.' else parent / safe_name(name)
    return [dict(f, target=directory(components[f['component']]['directory']) / safe_name(f['name']))
            for f in tables['File']]
