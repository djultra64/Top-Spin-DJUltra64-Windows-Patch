/* Own native bootstrap contract; no original game code/assets. djultra64. */
#define CALL __attribute__((stdcall))
typedef unsigned int U32;
extern void *iat_GetModuleFileNameA,*iat_GetProcAddress,*iat_LoadLibraryA,*iat_GetModuleHandleA;
extern void *iat_CreateFileA,*iat_WriteFile,*iat_CloseHandle,*iat_ExitProcess;
#define API(name,result,...) ((result(CALL*)(__VA_ARGS__))iat_##name)
extern int portable_path(void*,void*,char*,U32,void*);
static char actual[512],expected[512];
static void finish(int result){
    const char *text=result?"FAIL_BOOTSTRAP\r\n":"ABSOLUTE_LOCAL_DLL_BOOTSTRAP_AND_ORIGINAL_DIRECTORY_RESULT_PASS\r\n";
    U32 length=0,written=0;void *file;
    while(text[length])length++;
    file=API(CreateFileA,void*,const char*,U32,U32,void*,U32,U32,void*)("native-bootstrap-contract.txt",0x40000000,0,0,2,0x80,0);
    if(file!=(void*)-1){API(WriteFile,int,void*,const void*,U32,U32*,void*)(file,text,length,&written,0);API(CloseHandle,int,void*)(file);}
    API(ExitProcess,void,U32)((U32)result);for(;;){}
}
void _start(void){
    U32 n,i;void *module;int(CALL *initialize)(void);
    *(void**)0x6ec0d0=iat_GetModuleFileNameA;
    *(void**)0x6ec1dc=iat_LoadLibraryA;
    *(void**)0x6ec1e0=iat_GetProcAddress;
    if(API(GetModuleHandleA,void*,const char*)("djultra-input.dll"))finish(1);
    if(portable_path(0,0,actual,512,0)!=1)finish(2);
    n=API(GetModuleFileNameA,U32,void*,char*,U32)(0,expected,512);
    while(n&&expected[n-1]!='\\')n--;
    if(n<=3)finish(3);expected[n-1]=0;
    for(i=0;actual[i]&&actual[i]==expected[i];i++){}
    if(actual[i]!=expected[i])finish(4);
    module=API(GetModuleHandleA,void*,const char*)("djultra-input.dll");if(!module)finish(5);
    initialize=(int(CALL*)(void))API(GetProcAddress,void*,void*,const char*)(module,"DjultraInitialize");
    if(!initialize||initialize()!=3)finish(6);
    finish(0);
}
