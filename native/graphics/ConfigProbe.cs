// Own diagnostic of the official configuration API. djultra64.
using System;using System.IO;using System.Runtime.InteropServices;
class ConfigProbe {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)]static extern IntPtr LoadLibrary(string s);
 [DllImport("kernel32.dll",CharSet=CharSet.Ansi)]static extern IntPtr GetProcAddress(IntPtr m,string n);
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate IntPtr Init();
 [UnmanagedFunctionPointer(CallingConvention.ThisCall)]delegate IntPtr GetConfig(IntPtr self);
 [UnmanagedFunctionPointer(CallingConvention.ThisCall)] [return:MarshalAs(UnmanagedType.I1)]delegate bool ReadConfig(IntPtr self,IntPtr config,[MarshalAs(UnmanagedType.LPStr)]string path,IntPtr debug);
 static int Main(){try{string root=AppDomain.CurrentDomain.BaseDirectory;IntPtr lib=LoadLibrary(Path.Combine(root,"dgVoodooAPI.dll"));Init init=(Init)Marshal.GetDelegateForFunctionPointer(GetProcAddress(lib,"dgVoodoo_API_Init"),typeof(Init));IntPtr factory=init();GetConfig get=(GetConfig)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(Marshal.ReadIntPtr(factory),4),typeof(GetConfig));IntPtr obj=get(factory);ReadConfig read=(ReadConfig)Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj),12),typeof(ReadConfig));byte[] raw=File.ReadAllBytes(Path.Combine(root,"default-config.bin"));IntPtr config=Marshal.AllocHGlobal(raw.Length);Marshal.Copy(raw,0,config,raw.Length);bool ok=read(obj,config,Path.Combine(root,"dgVoodoo.conf"),IntPtr.Zero);Console.WriteLine("READ="+ok+" WIDTH="+Marshal.ReadInt32(config,100)+" HEIGHT="+Marshal.ReadInt32(config,104)+" PASS="+Marshal.ReadByte(config,128)+" APPCONTROL="+Marshal.ReadByte(config,129)+" WINDOWED="+Marshal.ReadByte(config,32));Marshal.FreeHGlobal(config);return ok?0:1;}catch(Exception e){Console.WriteLine(e);return 1;}}
}
