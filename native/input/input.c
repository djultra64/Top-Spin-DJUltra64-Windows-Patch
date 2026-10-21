/* Native per-process controller prompts. Own work: djultra64.
 * No original code/assets, input injection, DRM changes or global hooks.
 * SDL is dynamically loaded beside this DLL; keyboard state is read only while
 * this process owns the foreground window. Only activity/family is retained.
 */
#include "policy.h"
#include "engine.h"
#define STDCALL __attribute__((stdcall))
#define THISCALL __attribute__((thiscall))
typedef unsigned int U32;
typedef unsigned short U16;
typedef unsigned char U8;
typedef short I16;
#define IMPORT(name) extern void *iat_##name
IMPORT(GetModuleHandleA);IMPORT(GetModuleFileNameA);IMPORT(GetProcAddress);
IMPORT(LoadLibraryA);IMPORT(GetEnvironmentVariableA);IMPORT(GetTickCount);
IMPORT(VirtualAlloc);IMPORT(VirtualProtect);IMPORT(FlushInstructionCache);
IMPORT(GetCurrentProcess);IMPORT(GetCurrentProcessId);
IMPORT(CreateFileA);IMPORT(WriteFile);IMPORT(CloseHandle);
IMPORT(GetAsyncKeyState);IMPORT(GetForegroundWindow);IMPORT(GetWindowThreadProcessId);
#define API(name,result,...) ((result (STDCALL *)(__VA_ARGS__))iat_##name)
static void *our_module;
static int initialized,active_family,manual_family,pad_count,static_prompts;
static U8 positions[8]={0,1,2,3,4,5,6,7};
static U8 previous_keys[256];
static U32 last_poll,last_scan;
static int polled,scanned;
typedef struct Pad {U32 id;void *handle;U32 buttons;I16 axes[6];int family;} Pad;
static Pad pads[16];
static U32 active_pad;
static U8 (*s_init)(U32);
static U8 (*s_hint)(const char*,const char*);
static U32 *(*s_list)(int*);
static void (*s_free)(void*);
static void *(*s_open)(U32);
static void (*s_close)(void*);
static void (*s_update)(void);
static int (*s_type)(void*);
static U16 (*s_vendor)(void*);
static U16 (*s_product)(void*);
static U8 (*s_button)(void*,int);
static I16 (*s_axis)(void*,int);
static void *sdl;
static void *trampoline;
static void *engine_trampoline;
typedef void *(THISCALL *GlyphFn)(void*,U32);

static int equal(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static int absint(int v){return v<0?-v:v;}
static void copy(U8*d,const U8*s,U32 n){while(n--)*d++=*s++;}
static int family_of(void *handle){
    int kind=s_type(handle);U16 vendor=s_vendor(handle);
    if(vendor==0x28de)return 6; /* Steam virtual device can hide the real family. */
    if(kind==2)return 1;
    if(kind==3)return 2;
    if(kind==5)return 3;
    if(kind==6)return 4;
    if(kind>=7&&kind<=10)return 5;
    return 6;
}

static void scan_pads(void){
    int count=0,i,j,present;U32*ids=s_list(&count);
    if(!ids||count<0||count>256){if(ids)s_free(ids);return;}
    for(i=0;i<16;i++)if(pads[i].handle){
        present=0;for(j=0;j<count;j++)if(ids[j]==pads[i].id)present=1;
        if(!present){
            if(active_pad==pads[i].id){active_pad=0;active_family=0;}
            s_close(pads[i].handle);pads[i].handle=0;
        }
    }
    for(i=0;i<count;i++){
        present=0;for(j=0;j<16;j++)if(pads[j].handle&&pads[j].id==ids[i])present=1;
        if(present)continue;
        for(j=0;j<16;j++)if(!pads[j].handle){
            void *handle=s_open(ids[i]);int k;
            if(!handle)break;
            pads[j].id=ids[i];pads[j].handle=handle;pads[j].buttons=0;
            pads[j].family=family_of(handle);for(k=0;k<6;k++)pads[j].axes[k]=0;
            break;
        }
    }
    s_free(ids);pad_count=0;for(i=0;i<16;i++)if(pads[i].handle)pad_count++;
}

int STDCALL DjultraPoll(void){
    U32 now=API(GetTickCount,U32,void)();int i,k;
    if(polled&&(U32)(now-last_poll)<16)return active_family;
    polled=1;last_poll=now;
    if(sdl){
        s_update();
        if(!scanned||(U32)(now-last_scan)>=500){scan_pads();last_scan=now;scanned=1;}
        for(i=0;i<16;i++)if(pads[i].handle){
            U32 buttons=0;int moved=0;
            for(k=0;k<15;k++)if(s_button(pads[i].handle,k))buttons|=1u<<k;
            for(k=0;k<6;k++){
                I16 value=s_axis(pads[i].handle,k);
                if(absint(value)>8192&&absint((int)value-pads[i].axes[k])>1638)moved=1;
                pads[i].axes[k]=value;
            }
            if((buttons&~pads[i].buttons)||moved){
                active_pad=pads[i].id;active_family=manual_family?manual_family:pads[i].family;
            }
            pads[i].buttons=buttons;
        }
    }
    /* No system-wide keyboard hook. Do not sample another application's keys. */
    {
        void *window=API(GetForegroundWindow,void*,void)();U32 owner=0;
        API(GetWindowThreadProcessId,U32,void*,U32*)(window,&owner);
        if(owner==API(GetCurrentProcessId,U32,void)()){
            for(i=8;i<256;i++){
                U8 down=(API(GetAsyncKeyState,I16,int)(i)&0x8000)?1:0;
                if(down&&!previous_keys[i]){active_family=0;active_pad=0;}
                previous_keys[i]=down;
            }
        }
    }
    return active_family;
}

static void *(THISCALL glyph_hook)(void *font,U32 code){
    /* Original ABI consumes a WORD. Real callers can leave pointer bits in
       the high half of the pushed register after writing only SI. */
    U32 mapped;U32*fields=(U32*)font;code=(U16)code;mapped=code;
    DjultraPoll();
    /* Only our exact added range identifies an extended font. The game uses
       several atlas sizes for button prompts, including the regular UI font. */
    if(!static_prompts&&active_family&&fields[8]>0&&fields[8]<512){
        U16*ranges=(U16*)fields[9];U32 i;
        for(i=0;i<fields[8];i++)if(ranges[i*2]==0xe000&&ranges[i*2+1]==0xe02f){
            mapped=dj_glyph_code(code,active_family,positions);break;
        }
    }
    return ((GlyphFn)trampoline)(font,mapped);
}

static int install_glyph_hook(void){
    static const U8 expected[6]={0x55,0x66,0x8b,0x6c,0x24,0x08};
    U8 *base=API(GetModuleHandleA,void*,const char*)(0),*target=(U8*)0x612d50;
    U32 pe_offset,size,old,ignored;U8*code;int i;
    if(base!=(U8*)0x400000||*(U16*)base!=0x5a4d)return 0;
    pe_offset=*(U32*)(base+0x3c);
    if(pe_offset>4096||*(U32*)(base+pe_offset)!=0x4550)return 0;
    size=*(U32*)(base+pe_offset+24+56);
    if(size<0x213000||*(U16*)(base+pe_offset+4)!=0x14c)return 0;
    for(i=0;i<6;i++)if(target[i]!=expected[i])return 0;
    code=API(VirtualAlloc,void*,void*,U32,U32,U32)(0,32,0x3000,4);
    if(!code)return 0;
    copy(code,target,6);code[6]=0xe9;*(U32*)(code+7)=(U32)(target+6)-(U32)(code+11);
    if(!API(VirtualProtect,int,void*,U32,U32,U32*)(code,32,0x20,&ignored))return 0;
    if(!API(VirtualProtect,int,void*,U32,U32,U32*)(target,6,0x40,&old))return 0;
    trampoline=code;
    target[0]=0xe9;*(U32*)(target+1)=(U32)glyph_hook-(U32)(target+5);target[5]=0x90;
    API(VirtualProtect,int,void*,U32,U32,U32*)(target,6,old,&ignored);
    API(FlushInstructionCache,int,void*,void*,U32)(API(GetCurrentProcess,void*,void)(),target,6);
    return 1;
}

/* The game's joystick reader uses cdecl(index, state). SDL slots stay stable
   across a disconnect; a missing slot produces released buttons and axes.
   This is per-process adaptation, never a virtual device or keyboard event. */
int DjultraReadController(int index,void *state){
    int i;U32 buttons=0;I16 axes[6]={0,0,0,0,0,0};Pad *pad;
    if(!sdl||index<1||index>4){
        if(engine_trampoline)return ((int(*)(int,void*))engine_trampoline)(index,state);
        return (int)0x80004005u;
    }
    DjultraPoll();pad=&pads[index-1];
    if(pad->handle){
        for(i=0;i<15;i++)if(s_button(pad->handle,i))buttons|=1u<<i;
        for(i=0;i<6;i++)axes[i]=s_axis(pad->handle,i);
    }
    if(!dj_engine_state(state,360,buttons,axes,pad->handle!=0)||!pad->handle)
        return (int)0x80004005u;
    return 0;
}

static int install_engine_hook(void){
    static const U8 expected[6]={0x55,0x8b,0xec,0x83,0xe4,0xf8};
    U8 *base=API(GetModuleHandleA,void*,const char*)(0),*target=(U8*)0x52d1e0,*code;
    U32 pe_offset,old,ignored;int i;
    if(base!=(U8*)0x400000||*(U16*)base!=0x5a4d)return 0;
    pe_offset=*(U32*)(base+0x3c);
    if(pe_offset>4096||*(U32*)(base+pe_offset)!=0x4550||
       *(U32*)(base+pe_offset+24+56)<0x213000)return 0;
    for(i=0;i<6;i++)if(target[i]!=expected[i])return 0;
    code=API(VirtualAlloc,void*,void*,U32,U32,U32)(0,32,0x3000,4);
    if(!code)return 0;
    copy(code,target,6);code[6]=0xe9;*(U32*)(code+7)=(U32)(target+6)-(U32)(code+11);
    if(!API(VirtualProtect,int,void*,U32,U32,U32*)(code,32,0x20,&ignored))return 0;
    if(!API(VirtualProtect,int,void*,U32,U32,U32*)(target,6,0x40,&old))return 0;
    engine_trampoline=code;
    target[0]=0xe9;*(U32*)(target+1)=(U32)DjultraReadController-(U32)(target+5);target[5]=0x90;
    API(VirtualProtect,int,void*,U32,U32,U32*)(target,6,old,&ignored);
    API(FlushInstructionCache,int,void*,void*,U32)(API(GetCurrentProcess,void*,void)(),target,6);
    return 1;
}

static void write_local_status(const char *name,const char *message);
static void quit_status(const char *message){write_local_status(".portable\\quit-status.txt",message);}
/* Only the separately registered MainMenu method can request game exit. */
int THISCALL DjultraQuitGame(void *scene,void *params){
    U8 *manager;U32 *value;
    (void)scene;
    /* Original Career calls have no arguments. Only our explicitly marked
       menu action is allowed to request global exit. FArgumentList/FValue
       stay owned by the dispatcher; this callback never modifies them. */
    if(!params||*(U32*)((U8*)params+0x88)!=1){quit_status("ignored: count\r\n");return 0;}
    value=*(U32**)((U8*)params+0x84);
    if(!value||value[0]!=2||!value[2]){quit_status("ignored: type\r\n");return 0;}
    if(!equal((const char*)value[2],"djultra64.quit-game")){quit_status("ignored: marker\r\n");return 0;}
    manager=*(U8**)0xa4af20;
    if(manager&&!manager[0x4d1]){
        /* The original caller marks quit pending before asking; No clears it. */
        manager[0x4d1]=1;
        quit_status("confirmation requested\r\n");
        ((void(THISCALL*)(void*))0x5b9910)(manager);
        quit_status(manager[0x4d1]?"confirmed\r\n":"cancelled\r\n");
    }
    return 0;
}

void *THISCALL DjultraRegisterQuit(void *registry,const char *name,void *receiver,void *function){
    typedef void *(THISCALL *BindFn)(void*,const char*,void*,void*);
    BindFn bind=(BindFn)0x449a80;
    void *result=bind(registry,name,receiver,function);
    bind(registry,"DjultraQuitGame",receiver,DjultraQuitGame);
    quit_status("registered\r\n");
    return result;
}

static int install_quit_hook(void){
    static const U8 binding[]={0x68,0xb0,0x3c,0x44,0x00,0x56,0x68,0xbc,0xbb,0x6f,0x00,0x8b,0xce,0xe8,0x2b,0x0d,0x00,0x00};
    static const U8 binder[]={0x83,0xec,0x14,0x8b,0x54,0x24,0x18};
    static const U8 confirm[]={0xa1,0x50,0x80,0x7f,0x00,0x83,0xec,0x14};
    static const U8 getter[]={0xa1,0x20,0xaf,0xa4,0x00,0xc3};
    U8 *base=API(GetModuleHandleA,void*,const char*)(0);U32 pe,old,ignored;unsigned i;
    if(base!=(U8*)0x400000||*(U16*)base!=0x5a4d)return 0;
    pe=*(U32*)(base+0x3c);
    if(pe>4096||*(U32*)(base+pe)!=0x4550||*(U16*)(base+pe+4)!=0x14c||
       *(U32*)(base+pe+24+56)<0x64b000)return 0;
    for(i=0;i<sizeof(binding);i++)if(((U8*)0x448d43)[i]!=binding[i])return 0;
    for(i=0;i<sizeof(binder);i++)if(((U8*)0x449a80)[i]!=binder[i])return 0;
    if(!equal((const char*)0x6fbbbc,"TitleSelect"))return 0;
    for(i=0;i<sizeof(confirm);i++)if(((U8*)0x5b9910)[i]!=confirm[i])return 0;
    for(i=0;i<sizeof(getter);i++)if(((U8*)0x5b7220)[i]!=getter[i])return 0;
    if(!API(VirtualProtect,int,void*,U32,U32,U32*)((void*)0x448d50,5,0x40,&old))return 0;
    *(U32*)0x448d51=(U32)DjultraRegisterQuit-0x448d55;
    API(VirtualProtect,int,void*,U32,U32,U32*)((void*)0x448d50,5,old,&ignored);
    API(FlushInstructionCache,int,void*,void*,U32)(API(GetCurrentProcess,void*,void)(),(void*)0x448d50,5);
    return 1;
}

static void write_local_status(const char *name,const char *message){
    char path[1024];
    U32 n=API(GetModuleFileNameA,U32,void*,char*,U32)(0,path,900),i=0,written=0;void *file;
    if(!n||n>=900)return;
    while(n&&path[n-1]!='\\')n--;
    if(!n)return;
    while(name[i]){path[n+i]=name[i];i++;}path[n+i]=0;
    file=API(CreateFileA,void*,const char*,U32,U32,void*,U32,U32,void*)(path,0x40000000,1,0,2,0x80,0);
    if(file==(void*)-1)return;
    i=0;while(message[i])i++;
    API(WriteFile,int,void*,const void*,U32,U32*,void*)(file,message,i,&written,0);
    API(CloseHandle,int,void*)(file);
}

static void write_status(int status){

    char message[192];U32 cursor=0;int flag;
    const char *labels[4]={"SDL=","glyph hook=","controller adapter=","quit bridge="};
    for(flag=0;flag<4;flag++){
        const char *part=labels[flag];while(*part)message[cursor++]=*part++;
        part=(status&(1<<flag))?"ready":"unavailable";
        while(*part)message[cursor++]=*part++;
        if(flag!=3){message[cursor++]=';';message[cursor++]=' ';}
    }
    message[cursor++]='\r';message[cursor++]='\n';message[cursor]=0;
    write_local_status(".portable\\input-status.txt",message);
}

static int load_sdl(void){
    char path[1024];U32 n=API(GetModuleFileNameA,U32,void*,char*,U32)(our_module,path,1000);int i;
    const char *filename="SDL3.dll";
    if(!n||n>=1000)return 0;
    while(n&&path[n-1]!='\\')n--;
    if(!n)return 0;
    for(i=0;filename[i];i++)path[n+i]=filename[i];
    path[n+i]=0;
    sdl=API(LoadLibraryA,void*,const char*)(path);
    if(!sdl)return 0;
#define SDL_BIND(member,name) do {*(void**)(&member)=API(GetProcAddress,void*,void*,const char*)(sdl,name);if(!member){sdl=0;return 0;}}while(0)
    SDL_BIND(s_init,"SDL_InitSubSystem");SDL_BIND(s_hint,"SDL_SetHint");
    SDL_BIND(s_list,"SDL_GetGamepads");SDL_BIND(s_free,"SDL_free");
    SDL_BIND(s_open,"SDL_OpenGamepad");SDL_BIND(s_close,"SDL_CloseGamepad");
    SDL_BIND(s_update,"SDL_UpdateGamepads");SDL_BIND(s_type,"SDL_GetGamepadType");
    SDL_BIND(s_vendor,"SDL_GetGamepadVendor");SDL_BIND(s_product,"SDL_GetGamepadProduct");
    SDL_BIND(s_button,"SDL_GetGamepadButton");SDL_BIND(s_axis,"SDL_GetGamepadAxis");
#undef SDL_BIND
    s_hint("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS","1");
    if(!s_init(0x2000)){sdl=0;return 0;}
    return 1;
}

int STDCALL DjultraInitialize(void){
    static const char *families[6]={"xbox360","xbox","ps4","ps5","switch","unknown"};
    char value[64];U32 n;int i,status=0;
    if(initialized)return initialized;
    n=API(GetEnvironmentVariableA,U32,const char*,char*,U32)("TOPSPIN_STATIC_PROMPTS",value,64);
    static_prompts=n==1&&value[0]=='1';
    n=API(GetEnvironmentVariableA,U32,const char*,char*,U32)("TOPSPIN_CONTROLLER_FAMILY",value,64);
    if(n&&n<64)for(i=0;i<6;i++)if(equal(value,families[i]))manual_family=i+1;
    n=API(GetEnvironmentVariableA,U32,const char*,char*,U32)("TOPSPIN_MENU_POSITIONS",value,64);
    if(n==8)for(i=0;i<8;i++)if(value[i]>='0'&&value[i]<='7')positions[i]=(U8)(value[i]-'0');
    if(load_sdl())status|=1;
    if(install_glyph_hook())status|=2;
    if(sdl&&install_engine_hook())status|=4;
    if(install_quit_hook())status|=8;
    initialized=status?status:16;DjultraPoll();write_status(status);return initialized;
}
int STDCALL DjultraGetActiveFamily(void){return DjultraPoll();}
int STDCALL DjultraGetPadCount(void){DjultraPoll();return pad_count;}
U32 STDCALL DjultraResolveGlyphForTest(U32 code,int family){return dj_glyph_code(code,family,positions);}
int STDCALL DllMain(void *module,U32 reason,void *reserved){(void)reserved;if(reason==1)our_module=module;return 1;}
