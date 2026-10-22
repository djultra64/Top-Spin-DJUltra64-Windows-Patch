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


class ArtworkDownloadTests(unittest.TestCase):
    def synthetic_sources(self):
        import hashlib
        roles={'icon':(32,32), 'logo':(80,20), 'hero':(120,40),
               'portrait':(40,60), 'landscape':(90,40)}
        images={role:png(size) for role,size in roles.items()}
        sources={role:{'url':'https://cdn2.steamgriddb.com/grid/'+role+'.png',
                       'sha256':hashlib.sha256(images[role]).hexdigest(),
                       'width':size[0], 'height':size[1]} for role,size in roles.items()}
        return images,sources

    def test_missing_public_artwork_is_fetched_and_covers_all_five_slots(self):
        from unittest.mock import patch
        import launcher.steam_artwork as module
        images,sources=self.synthetic_sources();fetched=[];progress=[]
        def fetch(url):
            role=next(role for role,item in sources.items() if item['url']==url)
            fetched.append(role);return images[role]
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'ARTWORK_SOURCES',sources):
            game=Path(temporary)/'Game';game.mkdir()
            result=module.ensure_artwork(game,fetch=fetch,progress=progress.append)
            self.assertEqual(set(fetched),set(images))
            self.assertEqual(set(result),set(images))
            self.assertEqual({role:path.read_bytes() for role,path in result.items()},images)
            self.assertEqual(len(module.validate_artwork(game)),4)
            self.assertTrue(progress)
            second=module.ensure_artwork(game,fetch=lambda url:self.fail('Cached artwork was fetched again'))
            self.assertEqual(result,second)

    def test_valid_custom_art_is_preserved_and_incomplete_files_are_retried(self):
        from unittest.mock import patch
        import launcher.steam_artwork as module
        images,sources=self.synthetic_sources();requested=[]
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'ARTWORK_SOURCES',sources):
            game=Path(temporary)/'Game';cache=game/'artwork/steam';cache.mkdir(parents=True)
            custom=png((11,9),(1,2,3,255))
            (cache/'landscape.png').write_bytes(custom)
            (cache/'hero.png').write_bytes(b'incomplete PNG')
            def fetch(url):
                role=next(role for role,item in sources.items() if item['url']==url)
                requested.append(role);return images[role]
            module.ensure_artwork(game,fetch=fetch)
            self.assertNotIn('landscape',requested)
            self.assertEqual((cache/'landscape.png').read_bytes(),custom)
            self.assertEqual((cache/'hero.png').read_bytes(),images['hero'])

    def test_changed_remote_bytes_fail_before_any_cache_writes(self):
        from unittest.mock import patch
        import launcher.steam_artwork as module
        images,sources=self.synthetic_sources()
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'ARTWORK_SOURCES',sources):
            game=Path(temporary)/'Game';game.mkdir()
            def fetch(url):
                role=next(role for role,item in sources.items() if item['url']==url)
                return b'wrong server response' if role=='portrait' else images[role]
            with self.assertRaisesRegex(ValueError,'checksum'):
                module.ensure_artwork(game,fetch=fetch)
            self.assertFalse((game/'artwork').exists())

    def test_cache_write_failure_restores_incomplete_originals(self):
        from unittest.mock import patch
        from launcher.settings import atomic_write
        import launcher.steam_artwork as module
        images,sources=self.synthetic_sources();failed=False
        with tempfile.TemporaryDirectory() as temporary,patch.object(module,'ARTWORK_SOURCES',sources):
            game=Path(temporary)/'Game';cache=game/'artwork/steam';cache.mkdir(parents=True)
            original=b'old partial image';(cache/'icon.png').write_bytes(original)
            def fetch(url):
                return images[next(role for role,item in sources.items() if item['url']==url)]
            def fail_once(path,data):
                nonlocal failed
                if path.name=='hero.png' and not failed:
                    failed=True;raise OSError('Simulated disk error')
                atomic_write(path,data)
            with patch.object(module,'atomic_write',side_effect=fail_once),self.assertRaises(OSError):
                module.ensure_artwork(game,fetch=fetch)
            self.assertEqual({p.name:p.read_bytes() for p in cache.iterdir()},{'icon.png':original})

    def test_symlink_cache_is_rejected_before_network_access(self):
        import launcher.steam_artwork as module
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);game=root/'Game';game.mkdir();external=root/'external';external.mkdir()
            (game/'artwork').symlink_to(external,target_is_directory=True)
            with self.assertRaises(ValueError):
                module.ensure_artwork(game,fetch=lambda url:self.fail('Unsafe cache performed a download'))
            self.assertEqual(list(external.iterdir()),[])

    def test_network_fetch_is_bounded_and_rejects_unsafe_redirects(self):
        from unittest.mock import Mock,patch
        import launcher.steam_artwork as module
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.headers={};response.geturl.return_value=module.ARTWORK_SOURCES['icon']['url']
        response.read.return_value=b'small image bytes'
        opener=Mock();opener.open.return_value=response
        with patch.object(module.urllib.request,'build_opener',return_value=opener):
            self.assertEqual(module.fetch_artwork_image(module.ARTWORK_SOURCES['icon']['url']),b'small image bytes')
        self.assertEqual(opener.open.call_args.kwargs['timeout'],20)
        response.read.assert_called_once_with(module.MAX_ARTWORK_BYTES+1)
        for url in ['http://cdn2.steamgriddb.com/icon/a.png','https://unrelated.example/image.png',
                    'https://user:password@cdn2.steamgriddb.com/icon/a.png']:
            with self.subTest(url=url),self.assertRaises(ValueError):
                module.fetch_artwork_image(url)
        handler=module.ArtworkRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(None,None,302,'Redirect',{},'https://unrelated.example/image.png')
