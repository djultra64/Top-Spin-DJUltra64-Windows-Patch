import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tests.test_glyph_atlas import font_fixture

class GlyphInstallTests(unittest.TestCase):
    def test_only_font_payloads_change_and_source_archives_are_untouched(self):
        from tools.glyph_install import plan_font_archives
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'Media/Menu/RuiPC';folder.mkdir(parents=True)
            abc,dds=font_fixture();a=folder/'Base.rui';b=folder/'Base.ruirr'
            for path,name,data in [(a,'Fonts/Help_NovaBlackSSK.abc',abc),(b,'Fonts/Help_NovaBlackSSK.dds',dds)]:
                with zipfile.ZipFile(path,'w') as z:z.writestr(name,data);z.writestr('Scenes/original.sceneData',b'unchanged private payload')
            before={p:p.read_bytes() for p in [a,b]}
            with patch('tools.glyph_install.FONT_VARIANTS',{'Help_NovaBlackSSK':{(hashlib.sha256(abc).hexdigest(),hashlib.sha256(dds).hexdigest())}}):
                changes=plan_font_archives(root)
            self.assertEqual(set(changes),set(before))
            import io
            for path,data in changes.items():
                self.assertEqual(path.read_bytes(),before[path])
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    self.assertEqual(z.read('Scenes/original.sceneData'),b'unchanged private payload')
            with patch('tools.glyph_install.FONT_VARIANTS',{'Help_NovaBlackSSK':{('0'*64,'0'*64)}}):
                with self.assertRaisesRegex(ValueError,'Unsupported'):plan_font_archives(root)
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_unrelated_stored_entries_are_preserved_even_with_original_bad_crc(self):
        from tools.glyph_install import _replace
        import io,struct
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('Fonts/own.fixture',b'font');z.writestr('Textures/private.fixture',b'original')
        raw=bytearray(stream.getvalue())
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            info=z.getinfo('Textures/private.fixture');crc=info.CRC;at=info.header_offset
            n,e=struct.unpack_from('<HH',raw,at+26);raw[at+30+n+e]^=1
        changed=_replace(bytes(raw),'Fonts/own.fixture',b'extended font')
        with zipfile.ZipFile(io.BytesIO(changed)) as z:
            self.assertEqual(z.read('Fonts/own.fixture'),b'extended font')
            self.assertEqual(z.getinfo('Textures/private.fixture').CRC,crc)
        self.assertTrue(changed.startswith(bytes(raw[:raw.find(b'PK\x01\x02')])))

    def test_all_selected_fonts_in_one_archive_are_extended_and_each_pair_is_hash_checked(self):
        from tools.glyph_install import plan_font_archives
        import io
        from tools.glyph_atlas import parse_font
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'Media/RuiPC';folder.mkdir(parents=True)
            abc,dds=font_fixture();a=folder/'Base.rui';b=folder/'Base.ruirr'
            names=['Help_NovaBlackSSK','NovaBlackSSK_14','NovaBlackSSK_12','04b_11_12','NovaBlackSSK_24_Buttons']
            for path,extension,payload in [(a,'.abc',abc),(b,'.dds',dds)]:
                with zipfile.ZipFile(path,'w') as z:
                    for name in names:z.writestr('Fonts/'+name+extension,payload)
                    z.writestr('Scenes/other.fixture',b'preserve')
            known={name:{(hashlib.sha256(abc).hexdigest(),hashlib.sha256(dds).hexdigest())} for name in names}
            with patch('tools.glyph_install.FONT_VARIANTS',known):changes=plan_font_archives(root)
            with zipfile.ZipFile(io.BytesIO(changes[a])) as z:
                for name in names:
                    font=parse_font(z.read('Fonts/'+name+'.abc'))
                    self.assertEqual(font.codes[-48:],list(range(0xe000,0xe030)))
                self.assertEqual(z.read('Scenes/other.fixture'),b'preserve')
            known[names[-1]]={('0'*64,'0'*64)}
            with patch('tools.glyph_install.FONT_VARIANTS',known),self.assertRaisesRegex(ValueError,'Unsupported'):
                plan_font_archives(root)
