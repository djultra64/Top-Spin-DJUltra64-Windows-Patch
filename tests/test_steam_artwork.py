"""Synthetic artwork installation only; never writes an actual Steam profile."""
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from launcher.steam_artwork import install_artwork
from tools.steam_artwork import stage_artwork, ARTWORK_URLS


def png(size=(2,3),color=(20,40,80,180)):
    stream=io.BytesIO();Image.new('RGBA',size,color).save(stream,format='PNG');return stream.getvalue()


class ArtworkInstallTests(unittest.TestCase):
    def setup_game(self,root):
        game=root/'Game';source=game/'artwork/steam';source.mkdir(parents=True)
        for name in ['portrait','landscape','hero','logo']:(source/(name+'.png')).write_bytes(png())
        target=root/'Steam/userdata/123/config/shortcuts.vdf';target.parent.mkdir(parents=True)
        target.write_bytes(b'unchanged shortcut bytes')
        return game,target

    def test_correct_names_idempotence_and_unrelated_files_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,shortcut=self.setup_game(root)
            result=install_artwork(game,shortcut,2147484000)
            grid=shortcut.parent/'grid'
            self.assertEqual({p.name for p in result.installed}, {'2147484000.png','2147484000p.png','2147484000_hero.png','2147484000_logo.png'})
            (grid/'another-game.jpg').write_bytes(b'unrelated')
            before={p:p.read_bytes() for p in grid.iterdir() if p.is_file()}
            second=install_artwork(game,shortcut,2147484000)
            self.assertEqual(second.installed,());self.assertEqual(len(second.unchanged),4);self.assertEqual(second.backups,())
            self.assertEqual(shortcut.read_bytes(),b'unchanged shortcut bytes')
            self.assertEqual(before,{p:p.read_bytes() for p in grid.iterdir() if p.is_file()})

    def test_backups_existing_and_conflicting_extensions_without_removing_other_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,shortcut=self.setup_game(root);grid=shortcut.parent/'grid';grid.mkdir()
            existing={'42.png':b'old png','42.JPG':b'old jpg','42p.webp':b'old webp','42_hero.jpeg':b'old hero','420.jpg':b'other ID','42_custom.png':b'custom'}
            for name,value in existing.items():(grid/name).write_bytes(value)
            result=install_artwork(game,shortcut,42)
            self.assertEqual({p.read_bytes() for p in result.backups},{b'old png',b'old jpg',b'old webp',b'old hero'})
            for name in ['42.JPG','42p.webp','42_hero.jpeg']:self.assertFalse((grid/name).exists())
            self.assertEqual((grid/'420.jpg').read_bytes(),b'other ID');self.assertEqual((grid/'42_custom.png').read_bytes(),b'custom')
            self.assertEqual((grid/'42.png').read_bytes(),png())
            self.assertTrue(all(p.parent.parent==grid/'.topspin-artwork-backups' for p in result.backups))

    def test_partial_write_failure_restores_original_artwork_and_retains_backups(self):
        from unittest.mock import patch
        from launcher.settings import atomic_write
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,shortcut=self.setup_game(root);grid=shortcut.parent/'grid';grid.mkdir()
            (grid/'42.png').write_bytes(b'old landscape');(grid/'42p.png').write_bytes(b'old portrait')
            failed=False
            def fail_once(path,data):
                nonlocal failed
                if path==grid/'42p.png' and not failed:
                    failed=True;raise OSError('simulated write failure')
                return atomic_write(path,data)
            with patch('launcher.steam_artwork.atomic_write',side_effect=fail_once),self.assertRaises(OSError):
                install_artwork(game,shortcut,42)
            self.assertEqual((grid/'42.png').read_bytes(),b'old landscape')
            self.assertEqual((grid/'42p.png').read_bytes(),b'old portrait')
            backups=list((grid/'.topspin-artwork-backups').glob('*/*'))
            self.assertEqual({path.read_bytes() for path in backups},{b'old landscape',b'old portrait'})
            self.assertFalse((grid/'42_hero.png').exists())

    def test_invalid_ids_missing_assets_and_symlink_paths_do_not_touch_steam(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,shortcut=self.setup_game(root)
            for appid in [-1,0,2**32,True,'42']:
                with self.subTest(appid=appid),self.assertRaises(ValueError):install_artwork(game,shortcut,appid)
            (game/'artwork/steam/hero.png').unlink()
            with self.assertRaises(ValueError):install_artwork(game,shortcut,42)
            self.assertFalse((shortcut.parent/'grid').exists())
            (game/'artwork/steam/hero.png').write_bytes(png());external=root/'external';external.mkdir();(shortcut.parent/'grid').symlink_to(external,target_is_directory=True)
            with self.assertRaises(ValueError):install_artwork(game,shortcut,42)
            self.assertEqual(list(external.iterdir()),[])


class ArtworkBuildTests(unittest.TestCase):
    def test_build_classifies_grids_and_preserves_original_png_bytes(self):
        images={role:png((600,900) if role=='grid_a' else (920,430) if role=='grid_b' else (1280,300) if role=='hero' else (640,120) if role=='logo' else (256,256)) for role in ARTWORK_URLS}
        by_url={url:images[role] for role,url in ARTWORK_URLS.items()}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);report=stage_artwork(root,fetch=lambda url:by_url[url]);target=root/'artwork/steam'
            self.assertEqual((target/'portrait.png').read_bytes(),images['grid_a'])
            self.assertEqual((target/'landscape.png').read_bytes(),images['grid_b'])
            for name in ['icon.ico','sources.json','hero.png','logo.png','icon.png','logo-launcher.png','icon-launcher.png']:self.assertTrue((target/name).is_file(),name)
            for name,bounds in [('logo-launcher.png',(320,48)),('icon-launcher.png',(64,64))]:
                with Image.open(target/name) as image:self.assertLessEqual(image.width,bounds[0]);self.assertLessEqual(image.height,bounds[1]);self.assertEqual(image.mode,'RGBA')
            self.assertEqual(report['redistribution_status'],'No public redistribution rights established.')

    def test_real_downloads_are_restricted_to_the_ignored_private_build_folder(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp,patch('tools.steam_artwork.fetch_image',return_value=png()) as fetch:
            with self.assertRaises(ValueError):stage_artwork(Path(tmp))
            fetch.assert_not_called()

    def test_ambiguous_grids_or_non_png_are_rejected_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for raw in [b'not an image',png((32,32))]:
                with self.assertRaises(ValueError):stage_artwork(root,fetch=lambda url:raw)
                self.assertFalse((root/'artwork').exists())
