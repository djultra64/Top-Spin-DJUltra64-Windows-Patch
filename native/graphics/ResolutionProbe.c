/* Own freestanding native graphics probe. No game code or injected input. djultra64. */
#define CALL __attribute__((stdcall))
typedef unsigned int U;typedef void* P;
extern P iat_GetModuleHandleA,iat_GetModuleFileNameA,iat_LoadLibraryA,iat_GetProcAddress,iat_CreateFileA,iat_WriteFile,iat_CloseHandle,iat_ExitProcess,iat_Sleep;
#define K(name,R,...) ((R(CALL*)(__VA_ARGS__))iat_##name)
static P user,lib,mh;static char logdata[65536];static U length;
static void text(const char*s){while(*s&&length<65500)logdata[length++]=*s++;}
static void number(U n){char b[12];U i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i)logdata[length++]=b[--i];}
static void dimensions(const char*name,U w,U h){text(name);number(w);text("x");number(h);text("\r\n");}
static P proc(P module,const char*name){return K(GetProcAddress,P,P,const char*)(module,name);}
static P method(P object,U index){return (*(P**)object)[index];}
static P old_texture;
static int CALL texture_hook(P self,U*desc,P initial,P*out){dimensions("D3D11_TEXTURE2D ",desc[0],desc[1]);return ((int(CALL*)(P,U*,P,P*))old_texture)(self,desc,initial,out);}
static P old_create11;
static int CALL create_hook(P adapter,U driver,P software,U flags,P levels,U count,U sdk,P*device,U*level,P*context){
 int hr=((int(CALL*)(P,U,P,U,P,U,U,P*,U*,P*))old_create11)(adapter,driver,software,flags,levels,count,sdk,device,level,context);
 if(hr>=0){U old,ignored;P*slot=&(*(P**)*device)[5];P vp=proc(K(LoadLibraryA,P,const char*)("kernel32.dll"),"VirtualProtect");old_texture=*slot;((int(CALL*)(P,U,U,U*))vp)(slot,4,0x40,&old);*slot=(P)texture_hook;((int(CALL*)(P,U,U,U*))vp)(slot,4,old,&ignored);text("WRAPPER_D3D11_DEVICE\r\n");}return hr;
}
static int CALL wndproc(P window,U msg,U wp,U lp){return ((int(CALL*)(P,U,U,U))proc(user,"DefWindowProcA"))(window,msg,wp,lp);}
struct WndClass{U style;P callback;U extra,windowextra;P instance,icon,cursor,brush;const char*menu;const char*name;};
struct Present{U width,height,format,count,multisample,swap;P window;U windowed,depth,depthformat,flags,refresh,interval;};
struct Vertex{float x,y,z;U color;};
static struct WndClass cls;
static struct Present pp={3840,2160,22,1,0,1,0,1,0,0,0,0,0};
static struct Vertex triangle[3]={{-.8f,-.8f,.5f,0xffff0000},{0,.8f,.5f,0xff00ff00},{.8f,-.8f,.5f,0xff0000ff}};
static void finish(U code){P f;U n,i;char output[1024];K(GetModuleFileNameA,U,P,P,U)(0,output,1024);i=0;while(output[i])i++;while(i&&output[i-1]!=92)i--;{const char*name="native-resolution-probe.txt";while(*name)output[i++]=*name++;output[i]=0;}text(code?"FAIL\r\n":"PASS_NATIVE_RENDER_PRESENT\r\n");f=K(CreateFileA,P,const char*,U,U,P,U,U,P)(output,0x40000000,1,0,2,0x80,0);if(f!=(P)-1){K(WriteFile,int,P,P,U,U*,P)(f,logdata,length,&n,0);K(CloseHandle,int,P)(f);}K(ExitProcess,void,U)(f==(P)-1?15:code);for(;;){}}
void _start(void){P d3d,device=0,surface=0,window,dll11,create;U desc[8],i,msg[8];int hr;
 user=K(LoadLibraryA,P,const char*)("user32.dll");if(!user)finish(1);
 cls.callback=(P)wndproc;cls.instance=K(GetModuleHandleA,P,const char*)(0);cls.name="TopSpinNativeGraphicsProbe";
 if(!((U(CALL*)(P))proc(user,"RegisterClassA"))(&cls))finish(2);
 window=((P(CALL*)(U,const char*,const char*,U,int,int,int,int,P,P,P,P))proc(user,"CreateWindowExA"))(0,cls.name,"Top Spin private native graphics probe",0x90000000,0,0,1920,1080,0,0,cls.instance,0);if(!window)finish(3);
 mh=K(LoadLibraryA,P,const char*)("MinHook.x86.dll");if(!mh)finish(4);
 if(((int(CALL*)(void))proc(mh,"MH_Initialize"))()!=0)finish(5);
 dll11=K(LoadLibraryA,P,const char*)("d3d11.dll");create=proc(dll11,"D3D11CreateDevice");
 if(((int(CALL*)(P,P,P*))proc(mh,"MH_CreateHook"))(create,(P)create_hook,&old_create11)!=0)finish(6);
 if(((int(CALL*)(P))proc(mh,"MH_EnableHook"))(create)!=0)finish(7);
 lib=K(LoadLibraryA,P,const char*)("d3d8.dll");if(!lib)finish(8);
 d3d=((P(CALL*)(U))proc(lib,"Direct3DCreate8"))(220);if(!d3d)finish(9);
 pp.window=window;
 hr=((int(CALL*)(P,U,U,P,U,P,P*))method(d3d,15))(d3d,0,1,window,0x40,&pp,&device);if(hr<0)finish(10);
 hr=((int(CALL*)(P,U,U,P*))method(device,16))(device,0,0,&surface);if(hr<0)finish(11);
 hr=((int(CALL*)(P,P))method(surface,8))(surface,desc);if(hr<0)finish(12);dimensions("D3D8_LOGICAL_BACKBUFFER ",desc[6],desc[7]);
 ((int(CALL*)(P,U))method(device,76))(device,0x42);((int(CALL*)(P,U,U))method(device,50))(device,137,0);((int(CALL*)(P,U,U))method(device,50))(device,22,1);
 for(i=0;i<30;i++){
  ((int(CALL*)(P,U,P,U,U,float,U))method(device,36))(device,0,0,1,0xff183d63,1,0);
  ((int(CALL*)(P))method(device,34))(device);
  hr=((int(CALL*)(P,U,U,P,U))method(device,72))(device,4,1,triangle,16);if(hr<0)finish(13);
  ((int(CALL*)(P))method(device,35))(device);
  hr=((int(CALL*)(P,P,P,P,P))method(device,15))(device,0,0,0,0);if(hr<0)finish(14);
  while(((int(CALL*)(P,P,U,U,U))proc(user,"PeekMessageA"))(msg,0,0,0,1)){((int(CALL*)(P))proc(user,"TranslateMessage"))(msg);((int(CALL*)(P))proc(user,"DispatchMessageA"))(msg);}
  K(Sleep,void,U)(20);
 }
 {int rect[4];((int(CALL*)(P,P))proc(user,"GetClientRect"))(window,rect);dimensions("HWND_CLIENT ",(U)(rect[2]-rect[0]),(U)(rect[3]-rect[1]));}
 /* Exit only this diagnostic process; all hooks/resources are private to it. */
 finish(0);
}
