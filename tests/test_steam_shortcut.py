import tempfile
import unittest
from pathlib import Path
from launcher.steam import add_shortcut_bytes, write_shortcut, shortcut_spec

EMPTY=b'\x00shortcuts\x00\x08\x08'
EXISTING=(b'\x00shortcuts\x00\x000\x00\x01AppName\x00Other game\x00'
          b'\x07OpaqueValue\x00\x01\x02\x03\x04\x05\x06\x07\x08\x08\x08\x08')

class SteamShortcutTests(unittest.TestCase):
    def test_insertion_preserves_existing_records_byte_for_byte(self):
        spec=shortcut_spec(Path('/Games/Top Spin'),'linux')
        result,appid=add_shortcut_bytes(EXISTING,spec)
        self.assertIn(EXISTING[len(b'\x00shortcuts\x00'):-2],result)
        self.assertIn(b'Other game',result)
        self.assertIn(b'AppName\x00Top Spin\x00',result)
        self.assertEqual(add_shortcut_bytes(result,spec),(result,appid))

    def test_malformed_input_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shortcuts.vdf';path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                write_shortcut(path,shortcut_spec(Path('/game'),'linux'),steam_running=False)
            self.assertEqual(path.read_bytes(),b'corrupt')

    def test_explicit_write_requires_steam_closed_and_keeps_backup(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shortcuts.vdf';path.write_bytes(EMPTY)
            spec=shortcut_spec(Path('/Games/Top Spin'),'linux')
            with self.assertRaisesRegex(ValueError,'Close Steam'):
                write_shortcut(path,spec,steam_running=True)
            self.assertEqual(path.read_bytes(),EMPTY)
            write_shortcut(path,spec,steam_running=False)
            backups=list(path.parent.glob('shortcuts.vdf.*.bak'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_bytes(),EMPTY)
            old=path.read_bytes()
            write_shortcut(path,spec,steam_running=False)
            self.assertEqual(path.read_bytes(),old)
            self.assertEqual(len(list(path.parent.glob('shortcuts.vdf.*.bak'))),1)

    def test_shortcut_targets_launcher_and_preserves_path_spaces(self):
        linux=shortcut_spec(Path('/Games/Top Spin'),'linux')
        self.assertEqual(linux['Exe'],'"/Games/Top Spin/TopSpinLauncher.sh"')
        self.assertEqual(linux['LaunchOptions'],'--play')
        self.assertEqual(linux['StartDir'],'"/Games/Top Spin"')

    def test_previous_portable_shortcut_is_renamed_without_losing_its_id_or_unknown_fields(self):
        import struct
        legacy=(b'\x001\x00\x02appid\x00'+struct.pack('<I',123456)+
                b'\x01AppName\x00Top Spin Portable\x00'
                b'\x01Exe\x00"/Games/Top Spin/TopSpinLauncher.sh"\x00'
                b'\x01StartDir\x00"/Games/Top Spin"\x00'
                b'\x01LaunchOptions\x00--play\x00'
                b'\x07Unknown\x00\x01\x02\x03\x04\x05\x06\x07\x08\x08')
        original=EXISTING[:-2]+legacy+b'\x08\x08'
        spec=shortcut_spec(Path('/Games/Top Spin'),'linux')
        result,appid=add_shortcut_bytes(original,spec)
        self.assertEqual(appid,123456)
        self.assertEqual(result,original.replace(b'AppName\x00Top Spin Portable\x00',b'AppName\x00Top Spin\x00'))
        self.assertEqual(add_shortcut_bytes(result,spec),(result,123456))

    def test_refreshing_an_existing_icon_preserves_the_shortcut_id_and_other_games(self):
        spec=shortcut_spec(Path('/Games/Top Spin'),'linux')
        original,appid=add_shortcut_bytes(EXISTING,dict(spec,icon='/old/icon.png'))
        result,updated_id=add_shortcut_bytes(original,dict(spec,icon='/Games/Top Spin/artwork/steam/icon.png'))
        self.assertEqual(updated_id,appid)
        self.assertEqual(result,original.replace(b'/old/icon.png',b'/Games/Top Spin/artwork/steam/icon.png'))
        self.assertEqual(add_shortcut_bytes(result,dict(spec,icon='/Games/Top Spin/artwork/steam/icon.png')),(result,appid))
