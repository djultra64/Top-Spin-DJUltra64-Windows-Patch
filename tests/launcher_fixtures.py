"""Own synthetic PML fixture; no game assets, keys or original binaries. djultra64."""
from tools.pml import Node,Pml

def config_fixture():
    names=['Root','Video','Mappings','Security','DebugSettings','Res_X','Res_Y',
           'FullScreen','RefreshRate','AutoSynchronize','PreserveInput','PreserveSecurity']
    pml=Pml.__new__(Pml);pml.name_count=len(names)
    pml.dictionary=b'\0'.join(n.encode() for n in names)+b'\0'
    def node(name,properties):
        return Node(Pml.key(name),[],[(Pml.key(k),v) for k,v in properties])
    pml.root=Node(Pml.key('Root'),[
        node('Video',[('Res_X','1920'),('Res_Y','1080'),('FullScreen','true'),('RefreshRate','50')]),
        node('DebugSettings',[('AutoSynchronize','true')]),
        node('Mappings',[('PreserveInput','synthetic-input-sentinel')]),
        node('Security',[('PreserveSecurity','synthetic-security-sentinel')])],[])
    return pml.encode()
