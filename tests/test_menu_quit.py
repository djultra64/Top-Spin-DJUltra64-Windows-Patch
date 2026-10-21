"""Synthetic main-menu patch contracts. Own work: djultra64."""
import hashlib
import io
from pathlib import Path
import subprocess
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

LUA=Path('build/lua-5.0.3/bin/lua').resolve()

# All fixture tables and strings below are original test data.
FIXTURE=r'''
local matrices={MATRIX_A,MATRIX_B,MATRIX_C}
local c={};for i=1,210 do c[i]={Name='OwnControl'..i,NodeName='OwnNode'..i} end
c[5]={Name='group_exhibition',NodeName='SelectedText:Menu'}
c[6]={Name='group_options',NodeName='SelectedText5:Menu'}
c[97]={Name='group_options|SelectedText',NodeName='SelectedText5:Menu'}
c[150]={Name='Exhibition',NodeName='pht_exhibition'}
c[161]={Name='RootOptions',NodeName='pht_options'}
local nodes={
 {Name='pht_options',Type='Text',Flags=6,TextID='main_options',Visible=false,LPM=matrices[1]},
 {Name='group_exhibition',Type='Node',Flags=6,IsAnimated=false,LPM=matrices[2],Children={{Name='OwnSelected',Type='Template',Flags=0}}},
 {Name='group_options',Type='Node',Flags=23,IsAnimated=true,PositioningInfo=matrices[3],Children={{Name='SelectedText5:Menu',Type='Template',TemplateName='SelectedText',Flags=0,ChangedAttributes={['Menu']={ControlName='group_options'},['Menu|Interface|Color_pht_content|pht_content']={TextID='main_options'}}}}}
}
SceneData={Controls=c,Graph={Children={{Name='OwnCamera'},{Name='Menu',Children={{Name='OwnBackground'},{Name='OwnVideo'},{Name='main',PositioningInfo=MAIN_POSITION,Children=nodes}}}}},
 NodeTypes={[6]={Text=1,Node=1},[23]={Node=1},[0]={Template=2}},
 Actions={['Selection_Options(sound)']={{'OwnNavigationSound'},{'OwnActivateOptions','OwnHighlightOptions'}}},
 AnimationData={ClipsKeyframeData=ANIMATION_BYTES,OrderedNames={'own1','own2','own3','own4','own5','own6','own7','own8','own9','own10','own11','main'}}}
'''
for token,x,y in [('MATRIX_A',-137,-103),('MATRIX_B',-150,130),('MATRIX_C',-134,-115)]:
    data=struct.pack('<12f',x,y,0,*([1]*9))
    FIXTURE=FIXTURE.replace(token,'"'+''.join('\\%03d'%value for value in data)+'"')

_animation=bytearray(8164)
for start in [0xb80,0xef0,0x1860]:
    struct.pack_into('<III',_animation,start,11,0,10)
    for index,prop in enumerate([0,1,9,2,3,4,5,6,7,8]):
        struct.pack_into('<IIff',_animation,start+12+index*16,prop,1,0,1 if prop in [0,6,7,9] else 0)
for token,data in [('ANIMATION_BYTES',bytes(_animation)),('MAIN_POSITION',struct.pack('<12f',0,0,0,1,1,1,0,0,0,0,0,0))]:
    FIXTURE=FIXTURE.replace(token,'"'+''.join('\\%03d'%value for value in data)+'"')

EVENTS="Scenes.newmain={Controls={}};for i=1,210 do Scenes.newmain.Controls[i]={} end;Scenes.newmain.Controls[150]={Up=\"$Selection_Options('MoveUp')\",Down='Own next'};Scenes.newmain.Controls[161]={Down=\"$Selection_Exhibition('MoveDown')\",Up='Own previous',AButton='Own options'}"

@unittest.skipUnless(LUA.is_file(),'Local Lua 5.0.3 build needed')
class MenuQuitTests(unittest.TestCase):
    def archive(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            z.writestr('Scenes/newmain.sceneData',FIXTURE)
            z.writestr('Scenes/newmain.scene',EVENTS)
            z.writestr('Textures/own.fixture',b'keep this exact original test payload')
        return stream.getvalue()

    def test_unknown_or_already_patched_archive_is_rejected_before_execution(self):
        from tools.menu_quit import patch_main_menu
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            patch_main_menu(self.archive(),LUA)

    def test_member_hash_guard_rejects_tampered_chunk_before_running_compiler(self):
        from tools.menu_quit import patch_main_menu
        raw=self.archive()
        with patch('tools.menu_quit.SOURCE_SHA256',hashlib.sha256(raw).hexdigest()), \
             patch('tools.menu_quit.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'Unsupported main menu chunk'):
                patch_main_menu(raw,LUA)
            run.assert_not_called()

    def test_only_two_members_change_and_menu_delta_preserves_original_indices(self):
        from tools.menu_quit import patch_main_menu
        raw=self.archive()
        hashes={name:hashlib.sha256(data.encode()).hexdigest() for name,data in [('Scenes/newmain.sceneData',FIXTURE),('Scenes/newmain.scene',EVENTS)]}
        with patch('tools.menu_quit.SOURCE_SHA256',hashlib.sha256(raw).hexdigest()),patch('tools.menu_quit.MEMBER_SHA256',hashes),patch('tools.menu_quit.ANIMATION_SHA256',hashlib.sha256(_animation).hexdigest()):
            result=patch_main_menu(raw,LUA)
            with self.assertRaisesRegex(ValueError,'Unsupported'):patch_main_menu(result,LUA)
        with zipfile.ZipFile(io.BytesIO(raw)) as old,zipfile.ZipFile(io.BytesIO(result)) as new:
            self.assertEqual(old.namelist(),new.namelist())
            self.assertEqual(new.read('Textures/own.fixture'),old.read('Textures/own.fixture'))
            self.assertEqual(new.getinfo('Textures/own.fixture').header_offset,old.getinfo('Textures/own.fixture').header_offset)
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)
                (root/'animation-original.bin').write_bytes(_animation)
                for name in hashes:(root/Path(name).name).write_bytes(new.read(name))
                check=root/'check.lua'
                check.write_text('''local f=assert(loadfile(arg[1]));local e={};setfenv(f,e);f();local d=e.SceneData
assert(table.getn(d.Controls)==213);assert(d.Controls[150].Name=='Exhibition');assert(d.Controls[161].Name=='RootOptions')
assert(d.Controls[211].Name=='QuitGame');assert(d.Controls[212].Name=='group_quit');assert(d.Controls[213].Name=='group_quit|SelectedText')
assert(table.getn(d.AnimationData.OrderedNames)==12)
local nodes=d.Graph.Children[2].Children[3].Children;assert(table.getn(nodes)==5);assert(nodes[1].TextID=='main_options');assert(nodes[4].TextID=='ct_quit')
assert(nodes[5].Name=='group_quit');assert(nodes[5].IsAnimated==false)
assert(nodes[5].Children[1].ChangedAttributes['Menu|Interface|Color_pht_content|pht_content'].TextID=='ct_quit')
assert(d.NodeTypes[6].Text==2 and d.NodeTypes[6].Node==2 and d.NodeTypes[0].Template==3)
assert(d.Actions.QuitGame[1][1]=="PlaySound('Validate')");assert(d.Actions.QuitGame[2][1]=="this.DjultraQuitGame('djultra64.quit-game')")
local s={Scenes={}};f=assert(loadfile(arg[2]));setfenv(f,s);f();local c=s.Scenes.newmain.Controls
assert(table.getn(c)==213);assert(c[161].Down=="$Selection_Quit('MoveDown')");assert(c[150].Up=="$Selection_Quit('MoveUp')")
assert(c[211].Up=="$Selection_Options('MoveUp')");assert(c[211].Down=="$Selection_Exhibition('MoveDown')")
assert(c[211].AButton=='$QuitGame' and c[211].Start=='$QuitGame');assert(c[161].AButton=='Own options')
local base=d.Graph.Children[2].Children[3].PositioningInfo
assert(string.sub(base,5,8)==string.char(0,0,192,65))
local animation=d.AnimationData.ClipsKeyframeData
for _,at in ipairs({3016,3896,6312}) do assert(string.sub(animation,at+1,at+4)==string.char(0,0,192,65)) end
local original=assert(io.open(arg[3],'rb')):read('*a')
local count=0;for i=1,string.len(animation) do if string.byte(animation,i)~=string.byte(original,i) then count=count+1 end end
assert(count==6) -- Three 4-byte floats replaced; two bytes differ in each.
print('OWN_SYNTHETIC_MENU_DELTA_PASS')''')
                run=subprocess.run([str(LUA),str(check),str(root/'newmain.sceneData'),str(root/'newmain.scene'),str(root/'animation-original.bin')],capture_output=True,text=True)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertIn('OWN_SYNTHETIC_MENU_DELTA_PASS',run.stdout)
