"""Read Top Spin's PAM_PAK metadata without modifying the archive. djultra64.

Top Spin uses a 36-byte header, 8-byte data entries, 24-byte CRC lookup
entries and a string pool. CRCs identify full paths, case-insensitively.
Only uncompressed entries are currently supported; compressed data fails
explicitly rather than being silently misinterpreted.
"""
from pathlib import Path, PurePosixPath
import struct
import zlib

class PamArchive:
    def __init__(self, path: Path):
        self.data=path.read_bytes()
        data=self.data
        if data[:8]!=b'PAM_PAK\0' or len(data)<36:
            raise ValueError('Not a supported PAM archive')
        count=struct.unpack_from('<H',data,8)[0]
        names_size,base=struct.unpack_from('<II',data,12)
        metadata=36+count*8
        names=metadata+count*24
        if names+names_size>base or base>len(data):
            raise ValueError('Invalid PAM metadata layout')
        self.rows={}
        self.entries={}
        for i in range(count):
            key,index,name_offset,flags,parent,padding=struct.unpack_from('<6I',data,metadata+i*24)
            index &= 0xffff
            if index>=count or name_offset>=names_size or key in self.rows:
                raise ValueError('Invalid PAM lookup entry')
            end=data.find(b'\0',names+name_offset,names+names_size)
            if end<0:raise ValueError('Unterminated PAM name')
            name=data[names+name_offset:end].decode('cp1252')
            if name in ('','..') or any(c in name for c in '/\\:'):
                raise ValueError('Unsafe PAM name')
            size,offset=struct.unpack_from('<II',data,36+index*8)
            self.rows[key]={'name':name,'parent':parent,'size':size,'offset':offset}
        def full_path(key,seen=()):
            if key in seen:raise ValueError('Cyclic PAM directory tree')
            r=self.rows[key]
            return (full_path(r['parent'],seen+(key,))/r['name']
                    if r['parent'] else PurePosixPath(r['name']))
        for key,row in self.rows.items():
            name=str(full_path(key))
            checksum=zlib.crc32(name.lower().replace('/','\\').encode('cp1252'))
            if checksum!=key:raise ValueError(f'PAM path CRC mismatch: {name}')
            if row['offset']==0xffffffff:
                continue
            if row['size']>>30 or row['offset']<base or row['offset']+row['size']>len(data):
                raise ValueError(f'Unsupported or invalid PAM data entry: {name}')
            self.entries[name.lower()]=dict(row,path=name)

    def read(self, name: str) -> bytes:
        row=self.entries[name.replace('\\','/').lower()]
        result=self.data[row['offset']:row['offset']+row['size']]
        if result.startswith(b'PAM-'):
            raise ValueError('Compressed PAM entry unsupported')
        return result
