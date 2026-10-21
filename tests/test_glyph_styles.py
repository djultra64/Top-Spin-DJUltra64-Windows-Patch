"""Synthetic archives only. Own work: djultra64."""
import hashlib,io,json,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch

class PromptStyleTests(unittest.TestCase):
    def fixture(self,root):
        from tests.test_glyph_atlas import font_fixture
        from tools.glyph_atlas import extend_font
        abc,dds=font_fixture();abc=bytearray(abc)
        # Replace synthetic A..B with Return..Backspace.
        struct.pack_into('<HH',abc,24,0x2123,0x2124)
        abc,_=extend_font(bytes(abc),dds)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('Fonts/NovaBlackSSK_14.abc',abc)
            z.writestr('Scenes/fixture',b'unrelated payload')
        raw=stream.getvalue();path=root/'Media/RuiPC/Base.rui';path.parent.mkdir(parents=True);path.write_bytes(raw)
        return path,raw,{'Media/RuiPC/Base.rui':hashlib.sha256(raw).hexdigest()}

    def test_manual_styles_copy_selected_physical_record_then_auto_restores_exact_baseline(self):
        from launcher.glyphs import apply_prompt_style
        from tools.glyph_atlas import parse_font
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,raw,known=self.fixture(root)
            with patch('launcher.glyphs.BASELINE_SHA256',known):
                changed=apply_prompt_style(root,'switch','10234567')
                self.assertEqual(set(changed),{path})
                with zipfile.ZipFile(path) as z:
                    font=parse_font(z.read('Fonts/NovaBlackSSK_14.abc'))
                    self.assertEqual(z.read('Scenes/fixture'),b'unrelated payload')
                for original,position in [(0x2123,1),(0x2124,0)]:
                    self.assertEqual(font.glyphs[font.codes.index(original)],font.glyphs[font.codes.index(0xe000+4*8+position)])
                apply_prompt_style(root,'ps5','01234567')
                apply_prompt_style(root,'auto','01234567')
                self.assertEqual(path.read_bytes(),raw)

    def test_unknown_or_modified_source_is_rejected_without_writes(self):
        from launcher.glyphs import apply_prompt_style
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,raw,known=self.fixture(root)
            with patch('launcher.glyphs.BASELINE_SHA256',known):
                path.write_bytes(raw+b'changed')
                with self.assertRaisesRegex(ValueError,'baseline'):apply_prompt_style(root,'xbox360','01234567')
                self.assertFalse((root/'.portable/glyphs').exists())
                path.write_bytes(raw);apply_prompt_style(root,'xbox360','01234567')
                current=path.read_bytes();path.write_bytes(current+b'changed')
                with self.assertRaisesRegex(ValueError,'modified'):apply_prompt_style(root,'keyboard','01234567')
                self.assertEqual(path.read_bytes(),current+b'changed')

    def test_corrupt_backup_is_rejected_and_keyboard_restores_baseline(self):
        from launcher.glyphs import apply_prompt_style
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,raw,known=self.fixture(root)
            with patch('launcher.glyphs.BASELINE_SHA256',known):
                apply_prompt_style(root,'xbox360','01234567')
                apply_prompt_style(root,'keyboard','01234567');self.assertEqual(path.read_bytes(),raw)
                backup=root/'.portable/glyphs/baseline/Media/RuiPC/Base.rui';backup.write_bytes(b'bad')
                with self.assertRaisesRegex(ValueError,'backup'):apply_prompt_style(root,'switch','01234567')

    def test_write_failure_rolls_back_backup_and_keeps_original_archive(self):
        from launcher.glyphs import apply_prompt_style
        from launcher.settings import atomic_write
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path,raw,known=self.fixture(root);calls=[]
            def fail_once(target,data):
                calls.append(target)
                if len(calls)==2:raise OSError('simulated storage failure')
                atomic_write(target,data)
            with patch('launcher.glyphs.BASELINE_SHA256',known),patch('launcher.glyphs.atomic_write',side_effect=fail_once):
                with self.assertRaisesRegex(OSError,'storage'):apply_prompt_style(root,'xbox360','01234567')
            self.assertEqual(path.read_bytes(),raw)
            self.assertFalse((root/'.portable/glyphs/style.json').exists())
            self.assertFalse((root/'.portable/glyphs/baseline/Media/RuiPC/Base.rui').exists())
