"""Lossless reader/writer for Top Spin's binary PML tree. Author: djultra64."""
from dataclasses import dataclass
import struct
import zlib

@dataclass
class Node:
    key: int
    children: list
    properties: list

class Pml:
    def __init__(self, data: bytes):
        magic, tree_end, name_count = struct.unpack_from('<III', data)
        if magic != 0 or not 12 <= tree_end <= len(data):
            raise ValueError('Invalid PML header')
        self.dictionary = data[tree_end:]
        self.name_count = name_count
        names = self.dictionary.rstrip(b'\0').split(b'\0')
        if len(names) != name_count:
            raise ValueError('PML dictionary count mismatch')
        self.names = {zlib.crc32(n.lower()): n.decode('cp1252') for n in names}
        visited = set()
        def read(offset):
            if offset in visited or offset < 12 or offset + 12 > tree_end:
                raise ValueError('Invalid PML node offset')
            visited.add(offset)
            nc, np, key = struct.unpack_from('<III', data, offset)
            if nc + np > (tree_end - offset - 12) // 4:
                raise ValueError('Invalid PML table length')
            offsets = struct.unpack_from(f'<{nc + np}I', data, offset + 12)
            children = [read(o) for o in offsets[np:]]
            properties = []
            for o in offsets[:np]:
                if o < 12 or o + 4 >= tree_end:
                    raise ValueError('Invalid PML property offset')
                prop = struct.unpack_from('<I', data, o)[0]
                end = data.find(b'\0', o + 4, tree_end)
                if end < 0:
                    raise ValueError('Unterminated PML property')
                properties.append((prop, data[o + 4:end].decode('cp1252')))
            return Node(key, children, properties)
        self.root = read(12)

    @staticmethod
    def key(name):
        return zlib.crc32(name.lower().encode('cp1252'))

    def node(self, path):
        current = self.root
        for part in path.split('/') if path else []:
            current = next(n for n in current.children if n.key == self.key(part))
        return current

    def get(self, path, name):
        return next(value for key, value in self.node(path).properties if key == self.key(name))

    def set(self, path, name, value):
        node = self.node(path)
        key = self.key(name)
        for i, (k, _) in enumerate(node.properties):
            if k == key:
                node.properties[i] = (k, str(value))
                return
        raise KeyError(f'{path}/{name}')

    def encode(self):
        output = bytearray(12)
        def write(node):
            start = len(output)
            nc, np = len(node.children), len(node.properties)
            output.extend(struct.pack('<III', nc, np, node.key))
            table = len(output)
            output.extend(bytes(4 * (nc + np) + (4 if nc == 0 else 0)))
            offsets = []
            for key, value in node.properties:
                offsets.append(len(output))
                output.extend(struct.pack('<I', key) + value.encode('cp1252') + b'\0')
                output.extend(bytes((-len(output)) % 4))
            offsets.extend(write(child) for child in node.children)
            struct.pack_into(f'<{len(offsets)}I', output, table, *offsets)
            return start
        write(self.root)
        struct.pack_into('<III', output, 0, 0, len(output), self.name_count)
        output.extend(self.dictionary)
        return bytes(output)
