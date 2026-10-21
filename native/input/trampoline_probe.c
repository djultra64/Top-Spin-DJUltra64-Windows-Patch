/* Own isolated PE32 ABI harness. Never loads game code/assets. djultra64. */
#define CALL __attribute__((stdcall))
#define THIS __attribute__((thiscall))
typedef unsigned int U32;
typedef unsigned short U16;
typedef unsigned char U8;
extern void *iat_DjultraInitialize,*iat_GetModuleHandleA,*iat_GetTickCount;
extern void *iat_CreateFileA,*iat_WriteFile,*iat_CloseHandle,*iat_ExitProcess;
#define API(name,result,...) ((result(CALL*)(__VA_ARGS__))iat_##name)
typedef void *(THIS *Glyph)(void*,U32);
static U16 ranges[2]={0xe000,0xe02f};
static U32 font[16];
static const U32 codes[8]={0x2123,0x2124,0x2125,0x2126,0x2127,0x2128,0x212b,0x212c};
static void finish(int result){
    const char *message=result?"FAIL_NATIVE_HOOK\r\n":"REAL_TRAMPOLINE_THISCALL_168_CLEAN_AND_DIRTY_UTF16_CASES_PASS\r\n";
    U32 length=0,written=0;void *file;
    while(message[length])length++;
    file=API(CreateFileA,void*,const char*,U32,U32,void*,U32,U32,void*)("native-hook-contract.txt",0x40000000,0,0,2,0x80,0);
    if(file!=(void*)-1){API(WriteFile,int,void*,const void*,U32,U32*,void*)(file,message,length,&written,0);API(CloseHandle,int,void*)(file);}
    API(ExitProcess,void,U32)((U32)result);
    for(;;){}
}
void _start(void){
    U32 family,action,pattern,actual,expected;U8 *module;
    /* The loader reserves our own .fontstub section at the hook address. */
    if(API(DjultraInitialize,int,void)()!=3)finish(10);
    module=API(GetModuleHandleA,void*,const char*)("djultra-input.dll");
    if(!module)finish(11);
    font[6]=256;font[7]=1024;font[8]=1;font[9]=(U32)ranges;
    for(family=0;family<=6;family++)for(action=0;action<8;action++)for(pattern=0;pattern<3;pattern++){
        *(U32*)(module+DJ_ACTIVE_FAMILY_RVA)=family;
        *(U32*)(module+DJ_LAST_POLL_RVA)=API(GetTickCount,U32,void)();
        /* Real callers write SI then push ESI, leaving pointer bits above UTF-16. */
        actual=(U32)((Glyph)0x612d50)(font,codes[action]|(pattern==1?0x08a60000u:pattern==2?0xffff0000u:0));
        expected=family?0xe000+(family-1)*8+action:codes[action];
        if(actual!=expected)finish(20+family*8+action);
        if((U32)((Glyph)0x612d50)(font,65)!=65)finish(80);
    }
    font[7]=512;ranges[0]=0x20;ranges[1]=0x7e;
    *(U32*)(module+DJ_ACTIVE_FAMILY_RVA)=1;
    *(U32*)(module+DJ_LAST_POLL_RVA)=API(GetTickCount,U32,void)();
    if((U32)((Glyph)0x612d50)(font,0x2123)!=0x2123)finish(81);
    finish(0);
}
