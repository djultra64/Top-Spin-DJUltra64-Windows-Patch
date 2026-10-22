"""Generated ISO and cabinet safety fixtures only. Own work: djultra64."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
try:
    import pycdlib
except ImportError:
    pycdlib=None


def tables():
    return {'Directory':[{'id':'INSTALL','parent':'','name':'TopSpin'}],
            'Component':[{'id':'GAME','directory':'INSTALL'}],
            'File':[{'id':'TopSpin.exe','component':'GAME','name':'TopSpin.exe','size':12,'sequence':1},
                    {'id':'Config.pml','component':'GAME','name':'Config.pml','size':7,'sequence':2}],
            'Media':[{'disk':1,'last':1,'cabinet':'Media1.cab','source':''},
                     {'disk':2,'last':2,'cabinet':'','source':''}], 'MsiFileHash':[]}


def cabinet(names):
    rows=b''.join(struct.pack('<IIHHHH',size,0,0,0,0,0)+name.encode('ascii')+b'\0' for name,size in names)
    header=bytearray(36);header[:4]=b'MSCF';struct.pack_into('<I',header,8,36+len(rows));struct.pack_into('<I',header,16,36)
    struct.pack_into('<HHH',header,26,1,len(names),0)
    return bytes(header)+rows


class CabinetSafetyTests(unittest.TestCase):
    def test_source_aliases_reject_excessive_fields_before_building_products(self):
        from tools.iso_install import _source_aliases
        from tools.msi_reader import safe_name
        data=tables();item=dict(data['File'][0],name='one|two|three')
        with self.assertRaisesRegex(ValueError,'alias|filename'):_source_aliases(data,item)
        many='|'.join('own'+str(i) for i in range(30000))
        with patch('tools.iso_install.safe_name') as validate:
            with self.assertRaisesRegex(ValueError,'alias|filename'):_source_aliases(data,dict(item,name=many))
            validate.assert_not_called()
        with self.assertRaises(ValueError):safe_name(many)

    def test_nonlinux_publication_reserves_exclusively_and_keeps_source_on_collision(self):
        from tools.build_portable import publish_noreplace
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);staged=root/'stage';staged.mkdir();(staged/'own.txt').write_text('own file')
            destination=root/'destination';destination.mkdir()
            with patch('tools.build_portable.sys.platform','win32'):
                with self.assertRaises(FileExistsError):publish_noreplace(staged,destination)
                self.assertEqual(list(destination.iterdir()),[]);self.assertTrue(staged.is_dir())
                destination.rmdir();publish_noreplace(staged,destination)
            self.assertEqual((destination/'own.txt').read_text(),'own file');self.assertFalse(staged.exists())

    def test_standalone_build_preserves_racing_empty_destination_and_cleans_staging(self):
        from tools import build_portable
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';source.mkdir();(source/'TopSpin.msi').write_bytes(b'own fixture')
            loose=source/'program files/Atari/TopSpin';loose.mkdir(parents=True)
            (loose/'TopSpin.exe').write_bytes(b'own game exe');(loose/'Config.pml').write_bytes(b'own cfg')
            data=tables();data['Media']=[{'disk':1,'last':2,'cabinet':'','source':''}]
            destination=root/'racing';publish=build_portable.publish_noreplace
            def race(staged,target):
                target.mkdir()
                return publish(staged,target)
            with patch('tools.build_portable.read_tables',return_value=data), \
                 patch('tools.build_portable.publish_noreplace',side_effect=race):
                with self.assertRaises(FileExistsError):build_portable.build(source,destination)
            self.assertTrue(destination.is_dir());self.assertEqual(list(destination.iterdir()),[])
            self.assertFalse(list(root.glob('.topspin-cabs-*')))
            self.assertEqual((loose/'TopSpin.exe').read_bytes(),b'own game exe')

    def test_cabinet_table_rejects_traversal_duplicates_unknown_ids_and_size_mismatch(self):
        from tools.build_portable import validate_cabinet
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'own.cab'
            file.write_bytes(cabinet([('Own.id',12)]))
            self.assertEqual(validate_cabinet(file,{'Own.id':12}),{'own.id'})
            for entries in [[('../outside',12)],[('Own.id',12),('OWN.ID',12)],[('Unknown.id',12)],[('Own.id',13)]]:
                file.write_bytes(cabinet(entries))
                with self.subTest(entries=entries),self.assertRaises(ValueError):validate_cabinet(file,{'Own.id':12})

    def test_msi_name_rejects_windows_aliases_and_control_characters(self):
        from tools.msi_reader import safe_name,file_layout
        for name in ['evil?.cab','CON','trailing.','name\n.cab','a:b','../x','foo\\x']:
            with self.subTest(name=name),self.assertRaises(ValueError):safe_name(name)
        self.assertEqual(safe_name('SHORT~1.CAB|Long name.cab'),'Long name.cab')
        broken=tables();broken['File'][0]['size']=-1
        with self.assertRaises(ValueError):file_layout(broken)


@unittest.skipUnless(pycdlib,'Pinned pycdlib fixture dependency required')
class IsoInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.payload=self.root/'payload';binary=self.payload/'files/runtime/linux/bin/cabextract'
        binary.parent.mkdir(parents=True);binary.write_bytes(b'\x7fELFown synthetic extractor');binary.chmod(0o755)
        descriptor={'path':'files/runtime/linux/bin/cabextract','sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'executable':True}
        (self.payload/'manifest.json').write_text(json.dumps({'version':1,'platform':'linux','files':{'runtime/linux/bin/cabextract':descriptor}}))

    def make_iso(self,namespace='joliet',extra_msi=False,symlink=False,collision=False):
        image=pycdlib.PyCdlib();options={'interchange_level':3}
        if namespace=='joliet':options['joliet']=3
        if namespace=='rr':options['rock_ridge']='1.09'
        if namespace=='udf':options['udf']='2.60'
        image.new(**options)
        def paths(path,directory=False):
            raw='/'+path.upper().replace(' ','_') if path else '/'
            if not directory:raw+=';1'
            result={'iso_path':raw}
            if namespace=='joliet':result['joliet_path']='/'+path
            if namespace=='rr':result['rr_name']=path.split('/')[-1]
            if namespace=='udf':result['udf_path']='/'+path
            return result
        directories=['program files','program files/Atari','program files/Atari/TopSpin','Extras']
        for folder in directories:
            if namespace=='iso' and folder.startswith('program files'):continue
            image.add_directory(**paths(folder,True))
        ownfiles={'TopSpin.msi':b'own MSI fixture','Media1.cab':b'own cabinet bytes',
                  'program files/Atari/TopSpin/Config.pml':b'own cfg','Extras/Unrelated.exe':b'never execute or copy'}
        if extra_msi:ownfiles['Extras/TopSpin.msi']=b'ambiguous'
        if collision:ownfiles['topspin.MSI']=b'case collision'
        for name,data in ownfiles.items():
            if namespace=='iso' and name.startswith('program files'):continue
            kwargs=paths(name)
            if collision and name=='topspin.MSI':kwargs['iso_path']='/OTHER.MSI;1'
            image.add_fp(io.BytesIO(data),len(data),**kwargs)
        if symlink:image.add_symlink(symlink_path='/LINK.;1',rr_symlink_name='link',rr_path='../escape')
        destination=self.root/(namespace+str(extra_msi)+str(symlink)+str(collision)+'.iso')
        image.write(str(destination));image.close();return destination

    def _fake_build(self,source,destination,**kwargs):
        names={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
        expected={'TopSpin.msi','Media1.cab'}
        if (source/'program files').exists():expected.add('program files/Atari/TopSpin/Config.pml')
        self.assertEqual(names,expected)
        self.assertEqual(kwargs['cabextract'],self.payload/'files/runtime/linux/bin/cabextract')
        destination.mkdir();(destination/'TopSpin.exe').write_bytes(b'own game exe')
        loose=source/'program files/Atari/TopSpin/Config.pml'
        (destination/'Config.pml').write_bytes(loose.read_bytes() if loose.exists() else b'own cfg')
        return {'files':[{},{}]}

    def _fake_plan(self,game,payload):
        from tools.install_patch import build_install_integrity,json_bytes
        changes={'runtime/own.txt':b'own patch data'}
        changes['.portable/integrity.json']=json_bytes(build_install_integrity(game,changes))
        return changes,{'version':1,'author':'djultra64','platform':'linux','status':'validated','executable_files':[]}

    def test_iso9660_joliet_rockridge_and_udf_copy_only_declared_media_then_publish_atomically(self):
        from tools.iso_install import install_from_iso
        for namespace in ['iso','joliet','rr','udf']:
            iso=self.make_iso(namespace);original=iso.read_bytes();destination=self.root/'new parent'/namespace
            progress=[];data=tables()
            if namespace=='iso':data['Media']=[{'disk':1,'last':2,'cabinet':'Media1.cab','source':''}]
            with patch('tools.iso_install.read_tables',return_value=data),patch('tools.iso_install.build',side_effect=self._fake_build), \
                 patch('tools.iso_install.plan_install',side_effect=self._fake_plan),patch('tools.iso_install.SOURCE_SHA256',hashlib.sha256(b'own game exe').hexdigest()):
                result=install_from_iso(iso,destination,self.payload,progress=progress.append)
            self.assertTrue(result['installed']);self.assertEqual((destination/'Config.pml').read_bytes(),b'own cfg')
            self.assertEqual((destination/'runtime/own.txt').read_bytes(),b'own patch data')
            self.assertEqual(iso.read_bytes(),original);self.assertFalse((destination/'Extras').exists())
            self.assertTrue(any('ISO' in text for text in progress));self.assertFalse(list(destination.parent.glob('.topspin-install-*')))

    def test_existing_destination_and_cancel_preserve_everything(self):
        from tools.iso_install import install_from_iso
        iso=self.make_iso();destination=self.root/'existing';destination.mkdir()
        with self.assertRaises(FileExistsError):install_from_iso(iso,destination,self.payload)
        cancel=threading.Event();cancel.set();new=self.root/'new parent'/'cancelled'
        with self.assertRaises(InterruptedError):install_from_iso(iso,new,self.payload,cancel=cancel)
        self.assertFalse(new.exists());self.assertFalse(new.parent.exists())

    def test_ambiguous_msi_symlink_collision_and_corrupt_iso_are_rejected(self):
        from tools.iso_install import install_from_iso
        for iso in [self.make_iso(extra_msi=True),self.make_iso('rr',symlink=True),self.make_iso(collision=True)]:
            destination=self.root/'bad install'
            with self.subTest(iso=iso),self.assertRaises(ValueError):install_from_iso(iso,destination,self.payload)
            self.assertFalse(destination.exists())
        broken=self.root/'broken.iso';broken.write_bytes(b'not an ISO')
        with self.assertRaises(ValueError):install_from_iso(broken,self.root/'bad install',self.payload)

    def test_missing_cabinet_bad_msi_paths_and_patch_failure_never_publish(self):
        from tools.iso_install import install_from_iso
        iso=self.make_iso();destination=self.root/'failure parent'/'game'
        for malicious in ['../outside.cab','wrong.cab']:
            data=tables();data['Media'][0]['cabinet']=malicious
            with patch('tools.iso_install.read_tables',return_value=data),self.assertRaises((ValueError,FileNotFoundError)):
                install_from_iso(iso,destination,self.payload)
            self.assertFalse(destination.exists())
        with patch('tools.iso_install.read_tables',return_value=tables()),patch('tools.iso_install.build',side_effect=self._fake_build), \
             patch('tools.iso_install.plan_install',side_effect=ValueError('Unsupported executable')), \
             patch('tools.iso_install.SOURCE_SHA256',hashlib.sha256(b'own game exe').hexdigest()):
            with self.assertRaisesRegex(ValueError,'Unsupported'):install_from_iso(iso,destination,self.payload)
        self.assertFalse(destination.exists());self.assertFalse(destination.parent.exists())

    def test_racing_destination_is_preserved_and_staging_is_removed(self):
        from tools import iso_install
        iso=self.make_iso();destination=self.root/'racing';original=iso_install._publish
        def race(staged,target):
            target.mkdir();(target/'keep.txt').write_text('another operation owns this')
            return original(staged,target)
        with patch('tools.iso_install.read_tables',return_value=tables()),patch('tools.iso_install.build',side_effect=self._fake_build), \
             patch('tools.iso_install.plan_install',side_effect=self._fake_plan),patch('tools.iso_install._publish',side_effect=race), \
             patch('tools.iso_install.SOURCE_SHA256',hashlib.sha256(b'own game exe').hexdigest()):
            with self.assertRaises(FileExistsError):iso_install.install_from_iso(iso,destination,self.payload)
        self.assertEqual((destination/'keep.txt').read_text(),'another operation owns this')
        self.assertFalse((destination/'TopSpin.exe').exists());self.assertFalse(list(self.root.glob('.topspin-install-*')))

    def test_cancellation_during_copy_and_iso_bounds_remove_new_parent_directories(self):
        from tools.iso_install import install_from_iso
        iso=self.make_iso();destination=self.root/'new parent'/'cancelled';event=threading.Event()
        def progress(message):
            if message.startswith('Copying only'):event.set()
        with patch('tools.iso_install.read_tables',return_value=tables()):
            with self.assertRaises(InterruptedError):install_from_iso(iso,destination,self.payload,progress=progress,cancel=event)
        self.assertFalse(destination.parent.exists())
        with patch('tools.iso_install.MAX_ENTRY_BYTES',1):
            with self.assertRaisesRegex(ValueError,'bounds'):install_from_iso(iso,destination,self.payload)
        self.assertFalse(destination.parent.exists())

    def test_tampered_or_windows_extractor_manifest_is_rejected_before_opening_iso(self):
        from tools.iso_install import install_from_iso
        iso=self.make_iso();file=self.payload/'manifest.json';manifest=json.loads(file.read_text())
        for platform in ['windows','linux']:
            manifest['platform']=platform
            if platform=='linux':manifest['files']['runtime/linux/bin/cabextract']['sha256']='0'*64
            file.write_text(json.dumps(manifest))
            with self.subTest(platform=platform),patch.object(pycdlib.PyCdlib,'open') as opened:
                with self.assertRaises(ValueError):install_from_iso(iso,self.root/'bad',self.payload)
                opened.assert_not_called()
