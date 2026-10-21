/* Own isolated Linux ELF32 harness, never loads Top Spin. djultra64. */
#include "input.c"
static int protect_fail,flushes;
static U32 registrations;
static char last_status[80];
static void *registries[2],*receivers[2],*functions[2];
static const char *names[2];
static void *THISCALL own_binder(void *registry,const char *name,void *receiver,void *function){
    unsigned i=registrations++;
    if(i<2){registries[i]=registry;names[i]=name;receivers[i]=receiver;functions[i]=function;}
    return (void*)(0x12340001+i);
}
static U32 STDCALL file_name(void *m,char *p,U32 n){(void)m;(void)n;copy((U8*)p,(const U8*)"C:\\own\\probe.exe",17);return 16;}
static void *STDCALL create_file(const char*a,U32 b,U32 c,void*d,U32 e,U32 f,void*g){(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;return equal(a,"C:\\own\\.portable\\quit-status.txt")?(void*)1:(void*)-1;}
static int STDCALL write_file(void*a,const void*b,U32 c,U32*d,void*e){(void)a;(void)e;if(c>=80)return 0;copy((U8*)last_status,b,c);last_status[c]=0;*d=c;return 1;}
static int STDCALL close_file(void*a){(void)a;return 1;}
void *iat_GetModuleFileNameA=file_name,*iat_CreateFileA=create_file,*iat_WriteFile=write_file,*iat_CloseHandle=close_file;
static void *module_base=(void*)0x400000;
static void *STDCALL module(const char *name){(void)name;return module_base;}
static int STDCALL protect(void *p,U32 n,U32 mode,U32 *old){(void)p;(void)n;(void)mode;*old=0x20;return !protect_fail;}
static int STDCALL flush(void *p,void *q,U32 n){(void)p;(void)q;(void)n;flushes++;return 1;}
static void *STDCALL process(void){return (void*)-1;}
void *iat_GetModuleHandleA=module,*iat_VirtualProtect=protect;
void *iat_FlushInstructionCache=flush,*iat_GetCurrentProcess=process;
extern int abi_check(void *callback),registry_abi_check(void *callback);
void *probe_params;
static void quit(int code){__asm__ volatile("int $0x80"::"a"(1),"b"(code));__builtin_unreachable();}
void _start(void){
    static const U8 binding[]={0x68,0xb0,0x3c,0x44,0x00,0x56,0x68,0xbc,0xbb,0x6f,0x00,0x8b,0xce,0xe8,0x2b,0x0d,0x00,0x00};
    static const U8 confirm[]={0xa1,0x50,0x80,0x7f,0x00,0x83,0xec,0x14,
        0x89,0x0d,0x00,0x00,0xa0,0x00, /* own stub: record ECX */
        0xff,0x05,0x04,0x00,0xa0,0x00, /* count calls */
        0x80,0xb9,0xd1,0x04,0x00,0x00,0x01, /* require pending flag before modal */
        0x75,0x10,
        0x83,0x3d,0x08,0x00,0xa0,0x00,0x00, /* mode 0 Yes, 1 No */
        0x74,0x07,
        0xc6,0x81,0xd1,0x04,0x00,0x00,0x00,
        0x83,0xc4,0x14,0xc3};
    static const U8 getter[]={0xa1,0x20,0xaf,0xa4,0x00,0xc3};
    U8 *base=(void*)0x400000;U32 *m=(void*)0xa00000;int i;
    U32 args[35]={0},value[4]={2,0,0,0};
    static const char *invalid[]={"", "djultra64.quit", "djultra64.quit-game.extra", "Xdjultra64.quit-game", "djultra64.quit-game ", "djultra64.quit-gameX", "djultra64.quit\0-game"};
    /* mmap2(address,size,prot,flags,fd,offset), own anonymous private memory. */
    __asm__ volatile("push %%ebp;xor %%ebp,%%ebp;int $0x80;pop %%ebp"::"a"(192),"b"(base),"c"(0x650000),"d"(7),"S"(0x32),"D"(-1):"memory");
    *(U16*)base=0x5a4d;*(U32*)(base+0x3c)=0x80;*(U32*)(base+0x80)=0x4550;
    *(U16*)(base+0x84)=0x14c;*(U32*)(base+0x80+24+56)=0x650000;
    copy((void*)0x448d43,binding,sizeof(binding));
    copy((void*)0x6fbbbc,(const U8*)"TitleSelect",12);
    { /* Own binder stub begins with the guarded ABI entry, then forwards. */
        const U8 prefix[]={0x83,0xec,0x14,0x8b,0x54,0x24,0x18,0x83,0xc4,0x14,0xe9};
        copy((void*)0x449a80,prefix,sizeof(prefix));
        *(U32*)0x449a8b=(U32)own_binder-0x449a8f;
    }
    *(U32*)0x47e40d=0x4022a0;copy((void*)0x5b9910,confirm,sizeof(confirm));copy((void*)0x5b7220,getter,sizeof(getter));
    /* Guards fail without touching registration, including each expected byte. */
    module_base=(void*)0x410000;if(install_quit_hook())quit(21);module_base=base;
    *(U16*)base=0;if(install_quit_hook())quit(22);*(U16*)base=0x5a4d;
    *(U32*)(base+0x3c)=4097;if(install_quit_hook())quit(23);*(U32*)(base+0x3c)=0x80;
    *(U32*)(base+0x80)=0;if(install_quit_hook())quit(24);*(U32*)(base+0x80)=0x4550;
    *(U16*)(base+0x84)=0x8664;if(install_quit_hook())quit(25);*(U16*)(base+0x84)=0x14c;
    *(U32*)(base+0x80+24+56)=0x213000;if(install_quit_hook())quit(26);*(U32*)(base+0x80+24+56)=0x650000;
    for(i=0;i<(int)sizeof(binding);i++){((U8*)0x448d43)[i]^=1;if(install_quit_hook())quit(10);((U8*)0x448d43)[i]^=1;}
    for(i=0;i<8;i++){((U8*)0x5b9910)[i]^=1;if(install_quit_hook())quit(11);((U8*)0x5b9910)[i]^=1;}
    for(i=0;i<6;i++){((U8*)0x5b7220)[i]^=1;if(install_quit_hook())quit(12);((U8*)0x5b7220)[i]^=1;}
    for(i=0;i<7;i++){((U8*)0x449a80)[i]^=1;if(install_quit_hook())quit(60);((U8*)0x449a80)[i]^=1;}
    for(i=0;i<12;i++){((U8*)0x6fbbbc)[i]^=1;if(install_quit_hook())quit(61);((U8*)0x6fbbbc)[i]^=1;}
    protect_fail=1;if(install_quit_hook()||*(U32*)0x448d51!=0xd2b)quit(13);protect_fail=0;
    if(!install_quit_hook()||0x448d55+*(U32*)0x448d51!=(U32)DjultraRegisterQuit||flushes!=1)quit(14);
    if(registry_abi_check(DjultraRegisterQuit)||registrations!=2)quit(50);
    if(registries[0]!=(void*)0xa02000||registries[1]!=registries[0]||
       receivers[0]!=(void*)0xa03000||receivers[1]!=receivers[0]||
       functions[0]!=(void*)0x443cb0||functions[1]!=(void*)DjultraQuitGame||
       names[0]!=(void*)0x6fbbbc||!equal(names[1],"DjultraQuitGame"))quit(51);
    if(!equal(last_status,"registered\r\n"))quit(62);
    /* Every original zero-argument call, including Career, remains a no-op.
       Invalid manager poisons accidental access before the marker check. */
    *(void**)0xa4af20=(void*)1;
    if(abi_check(DjultraQuitGame)||m[1]||!equal(last_status,"ignored: count\r\n"))quit(30);
    probe_params=args;
    if(abi_check(DjultraQuitGame)||m[1])quit(31); /* zero arguments */
    args[34]=2;
    if(abi_check(DjultraQuitGame)||m[1])quit(32);
    args[34]=1;
    if(abi_check(DjultraQuitGame)||m[1])quit(33); /* null vector */
    args[33]=(U32)value;
    if(abi_check(DjultraQuitGame)||m[1])quit(34); /* null string */
    value[0]=1;value[2]=(U32)"djultra64.quit-game";
    if(abi_check(DjultraQuitGame)||m[1])quit(35); /* non-string value */
    value[0]=2;
    for(i=0;i<7;i++){
        value[2]=(U32)invalid[i];
        if(abi_check(DjultraQuitGame)||m[1])quit(36+i);
    }
    value[2]=(U32)"djultra64.quit-game";
    *(void**)0xa4af20=0;
    if(abi_check(DjultraQuitGame)||m[1])quit(15); /* null manager does nothing */
    *(void**)0xa4af20=(void*)0xa01000;
    if(abi_check(DjultraQuitGame)||m[0]!=0xa01000||m[1]!=1)quit(16);
    if(*(U8*)0xa014d1!=1||!equal(last_status,"confirmed\r\n"))quit(18); /* Yes preserves pending */
    if(abi_check(DjultraQuitGame)||m[1]!=1)quit(19); /* no duplicate pending */
    *(U8*)0xa014d1=0;m[2]=1;
    if(abi_check(DjultraQuitGame)||m[1]!=2||*(U8*)0xa014d1||!equal(last_status,"cancelled\r\n"))quit(20); /* No cancels */
    /* Shared original callback and other binding bytes remain untouched. */
    if(*(U8*)0x4022a0!=0||*(U32*)0x47e40d!=0x4022a0||*(U8*)0x448d43!=0x68||*(U8*)0x448d55!=0)quit(17);
    quit(0);
}
