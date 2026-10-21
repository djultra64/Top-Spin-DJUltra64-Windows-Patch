// Own process only: observe D3D11 resources produced by the D3D8 wrapper.
// No game code, no OS input injection. Author: djultra64.
using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using System.Drawing;
using System.Threading;
using System.Text;
using System.Diagnostics;

class ResolutionProbe {
 [DllImport("MinHook.x86.dll")] static extern int MH_Initialize();
 [DllImport("MinHook.x86.dll")] static extern int MH_CreateHook(IntPtr target,IntPtr detour,out IntPtr original);
 [DllImport("MinHook.x86.dll")] static extern int MH_EnableHook(IntPtr target);
 [DllImport("MinHook.x86.dll")] static extern int MH_DisableHook(IntPtr target);
 [DllImport("MinHook.x86.dll")] static extern int MH_Uninitialize();
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void DebugCall(IntPtr text);
 static DebugCall debugAnsi,debugWide;
 static void OnDebugAnsi(IntPtr text){Record("DGDEBUG "+Marshal.PtrToStringAnsi(text));}
 static void OnDebugWide(IntPtr text){Record("DGDEBUG "+Marshal.PtrToStringUni(text));}
 static void HookDebug(string name,DebugCall callback){IntPtr ignored;IntPtr target=GetProcAddress(LoadLibrary("kernel32.dll"),name);int status=MH_CreateHook(target,Marshal.GetFunctionPointerForDelegate(callback),out ignored);Record("DEBUG_HOOK "+name+"="+status);if(status==0)MH_EnableHook(target);}
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Create11Call(IntPtr adapter,int driver,IntPtr software,uint flags,IntPtr levels,uint levelCount,uint sdk,out IntPtr device,out int level,out IntPtr context);
 static Create11Call create11Original,create11Hook;
 static int OnCreate11(IntPtr adapter,int driver,IntPtr software,uint flags,IntPtr levels,uint levelCount,uint sdk,out IntPtr device,out int level,out IntPtr context) {
  int hr=create11Original(adapter,driver,software,flags,levels,levelCount,sdk,out device,out level,out context);Record("WRAPPER_D3D11_CREATE "+hr.ToString("x8")+" flags="+flags.ToString("x"));
  if(hr>=0) {
   textureOriginal=Get<TextureCall>(device,5);textureHook=OnTexture;textureSlot=IntPtr.Add(Marshal.ReadIntPtr(device),5*4);Set(textureSlot,Marshal.GetFunctionPointerForDelegate(textureHook));
   targetsOriginal=Get<TargetsCall>(context,33);targetsHook=OnTargets;targetsSlot=IntPtr.Add(Marshal.ReadIntPtr(context),33*4);Set(targetsSlot,Marshal.GetFunctionPointerForDelegate(targetsHook));
  }
  return hr;
 }

 [DllImport("d3d11.dll",CallingConvention=CallingConvention.StdCall)] static extern int D3D11CreateDevice(IntPtr adapter,int driver,IntPtr software,uint flags,int[] levels,uint levelCount,uint sdk,out IntPtr device,out int level,out IntPtr context);
 [DllImport("dxgi.dll",CallingConvention=CallingConvention.StdCall)] static extern int CreateDXGIFactory1(ref Guid iid,out IntPtr factory);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr LoadLibrary(string path);
 [DllImport("kernel32.dll",CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr module,string name);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern uint GetModuleFileName(IntPtr module,StringBuilder name,int length);
 [DllImport("kernel32.dll")] static extern bool VirtualProtect(IntPtr address,UIntPtr count,uint protection,out uint old);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void TargetsCall(IntPtr self,uint count,IntPtr views,IntPtr depth);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void ResourceCall(IntPtr self,out IntPtr resource);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate void DescCall(IntPtr self,IntPtr desc);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int TextureCall(IntPtr self,IntPtr desc,IntPtr data,out IntPtr texture);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SwapCall(IntPtr self,IntPtr device,IntPtr desc,out IntPtr swap);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SwapHwndCall(IntPtr self,IntPtr device,IntPtr hwnd,IntPtr desc,IntPtr full,IntPtr restrict,out IntPtr swap);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate IntPtr D3DCreate(uint sdk);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int DeviceCreate(IntPtr self,uint adapter,int type,IntPtr hwnd,uint behavior,ref PresentParameters pp,out IntPtr device);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int BackBuffer(IntPtr self,uint index,int type,out IntPtr surface);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SurfaceDesc(IntPtr self,IntPtr desc);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ClearCall(IntPtr self,uint count,IntPtr rects,uint flags,uint color,float z,uint stencil);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int PresentCall(IntPtr self,IntPtr source,IntPtr dest,IntPtr hwnd,IntPtr dirty);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SimpleCall(IntPtr self);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int UIntCall(IntPtr self,uint value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int StateCall(IntPtr self,uint state,uint value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int DrawCall(IntPtr self,uint type,uint count,IntPtr vertices,uint stride);
 [StructLayout(LayoutKind.Sequential)] struct Vertex {public float x,y,z;public uint color;public Vertex(float a,float b,uint c){x=a;y=b;z=0.5f;color=c;}}
 [StructLayout(LayoutKind.Sequential)] struct PresentParameters { public uint width,height,format,count,multisample,swap;public IntPtr hwnd;public int windowed,depth;public uint depthFormat,flags,refresh,interval; }
 static List<string> output=new List<string>();
 static HashSet<string> textures=new HashSet<string>();
 static TextureCall textureOriginal,textureHook;
 static SwapCall swapOriginal,swapHook;
 static SwapHwndCall hwndOriginal,hwndHook;
 static IntPtr textureSlot,swapSlot,hwndSlot,targetsSlot;
 static TargetsCall targetsOriginal,targetsHook;
 static HashSet<string> renderTargets=new HashSet<string>();
 static void OnTargets(IntPtr self,uint count,IntPtr views,IntPtr depth) {
   if(count>0&&views!=IntPtr.Zero) {
     IntPtr view=Marshal.ReadIntPtr(views);
     if(view!=IntPtr.Zero) {IntPtr resource;Get<ResourceCall>(view,7)(view,out resource);if(resource!=IntPtr.Zero){IntPtr desc=Marshal.AllocHGlobal(44);Get<DescCall>(resource,10)(resource,desc);string size=Marshal.ReadInt32(desc,0)+"x"+Marshal.ReadInt32(desc,4);if(renderTargets.Add(size))Record("D3D11_BOUND_RENDER_TARGET "+size);Marshal.FreeHGlobal(desc);Marshal.Release(resource);}}
   }
   targetsOriginal(self,count,views,depth);
 }
 static IntPtr Function(IntPtr obj,int index) {return Marshal.ReadIntPtr(Marshal.ReadIntPtr(obj),index*IntPtr.Size);}
 static T Get<T>(IntPtr obj,int index) where T:class {return Marshal.GetDelegateForFunctionPointer(Function(obj,index),typeof(T)) as T;}
 static void Set(IntPtr slot,IntPtr value) {uint old; if(!VirtualProtect(slot,(UIntPtr)IntPtr.Size,0x40,out old))throw new Exception("VirtualProtect failed");Marshal.WriteIntPtr(slot,value);uint ignored;VirtualProtect(slot,(UIntPtr)IntPtr.Size,old,out ignored);}
 static void Record(string line) {lock(output){output.Add(line);File.AppendAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"resolution-trace.txt"),line+Environment.NewLine);}}
 static int OnTexture(IntPtr self,IntPtr desc,IntPtr data,out IntPtr texture) {
   string key=Marshal.ReadInt32(desc,0)+"x"+Marshal.ReadInt32(desc,4)+" bind="+Marshal.ReadInt32(desc,32).ToString("x");
   lock(textures)if(textures.Add(key))Record("D3D11_TEXTURE2D "+key);
   return textureOriginal(self,desc,data,out texture);
 }
 static int OnSwap(IntPtr self,IntPtr device,IntPtr desc,out IntPtr swap) {
   Record("DXGI_SWAPCHAIN "+Marshal.ReadInt32(desc,0)+"x"+Marshal.ReadInt32(desc,4));
   return swapOriginal(self,device,desc,out swap);
 }
 static int OnSwapHwnd(IntPtr self,IntPtr device,IntPtr hwnd,IntPtr desc,IntPtr full,IntPtr restrict,out IntPtr swap) {
   Record("DXGI_SWAPCHAIN_HWND "+Marshal.ReadInt32(desc,0)+"x"+Marshal.ReadInt32(desc,4));
   return hwndOriginal(self,device,hwnd,desc,full,restrict,out swap);
 }
 [STAThread] static int Main(string[] args) {
   IntPtr real=IntPtr.Zero,context=IntPtr.Zero,factory=IntPtr.Zero,device=IntPtr.Zero,d3d=IntPtr.Zero,surface=IntPtr.Zero;
   int result=1;
   try {
     if(IntPtr.Size!=4)throw new Exception("Run x86 probe");
     Record("SCREEN "+Screen.PrimaryScreen.Bounds.Width+"x"+Screen.PrimaryScreen.Bounds.Height);
     int hr=0;Record("D3D11_DEVICE_CREATED");
     if(MH_Initialize()!=0)throw new Exception("MinHook init failed");
     debugAnsi=OnDebugAnsi;debugWide=OnDebugWide;HookDebug("OutputDebugStringA",debugAnsi);HookDebug("OutputDebugStringW",debugWide);IntPtr original11;create11Hook=OnCreate11;
     IntPtr create11=GetProcAddress(LoadLibrary("d3d11.dll"),"D3D11CreateDevice");
     int mh=MH_CreateHook(create11,Marshal.GetFunctionPointerForDelegate(create11Hook),out original11);if(mh!=0)throw new Exception("MinHook create="+mh);
     create11Original=(Create11Call)Marshal.GetDelegateForFunctionPointer(original11,typeof(Create11Call));if(MH_EnableHook(create11)!=0)throw new Exception("MinHook enable failed");
     Record("TEXTURE_VTABLE_HOOKED");Guid iid=new Guid("50c83a1c-e072-4c48-87b0-3630fa36a6d0");hr=CreateDXGIFactory1(ref iid,out factory);if(hr<0)Marshal.ThrowExceptionForHR(hr);
     Record("DXGI_FACTORY_CREATED");swapOriginal=Get<SwapCall>(factory,10);swapHook=OnSwap;swapSlot=IntPtr.Add(Marshal.ReadIntPtr(factory),10*4);Set(swapSlot,Marshal.GetFunctionPointerForDelegate(swapHook));
     hwndOriginal=Get<SwapHwndCall>(factory,15);hwndHook=OnSwapHwnd;hwndSlot=IntPtr.Add(Marshal.ReadIntPtr(factory),15*4);Set(hwndSlot,Marshal.GetFunctionPointerForDelegate(hwndHook));
     Record("SWAPCHAIN_VTABLE_HOOKED");using(Form form=new Form()) {
       form.Text="Top Spin private graphics resolution probe";form.ClientSize=new Size(1920,1080);form.StartPosition=FormStartPosition.CenterScreen;
       form.Show();Application.DoEvents();
       IntPtr library=LoadLibrary(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"d3d8.dll"));if(library==IntPtr.Zero)throw new Exception("Local wrapper not loaded");
       StringBuilder modulePath=new StringBuilder(1024);GetModuleFileName(library,modulePath,1024);Record("WRAPPER_LOADED "+modulePath.ToString());D3DCreate create=(D3DCreate)Marshal.GetDelegateForFunctionPointer(GetProcAddress(library,"Direct3DCreate8"),typeof(D3DCreate));d3d=create(220);if(d3d==IntPtr.Zero)throw new Exception("Direct3DCreate8 failed");
       Record("D3D8_CREATED");PresentParameters pp=new PresentParameters();pp.width=(args.Length>0&&args[0]=="4k")?3840u:1920u;pp.height=(args.Length>0&&args[0]=="4k")?2160u:1080u;pp.format=22;pp.count=1;pp.swap=1;pp.hwnd=form.Handle;pp.windowed=1;pp.interval=0;
       hr=Get<DeviceCreate>(d3d,15)(d3d,0,1,form.Handle,0x40,ref pp,out device);Record("CREATE_DEVICE_HRESULT "+hr.ToString("x8"));if(hr<0)Marshal.ThrowExceptionForHR(hr);
       Record("D3D8_DEVICE_CREATED");hr=Get<BackBuffer>(device,16)(device,0,0,out surface);if(hr<0)Marshal.ThrowExceptionForHR(hr);
       IntPtr desc=Marshal.AllocHGlobal(32);try {hr=Get<SurfaceDesc>(surface,8)(surface,desc);if(hr<0)Marshal.ThrowExceptionForHR(hr);Record("D3D8_LOGICAL_BACKBUFFER "+Marshal.ReadInt32(desc,24)+"x"+Marshal.ReadInt32(desc,28));}finally {Marshal.FreeHGlobal(desc);}
       ClearCall clear=Get<ClearCall>(device,36);PresentCall present=Get<PresentCall>(device,15);
       SimpleCall begin=Get<SimpleCall>(device,34),end=Get<SimpleCall>(device,35);
       Get<UIntCall>(device,76)(device,0x42);Get<StateCall>(device,50)(device,137,0);Get<StateCall>(device,50)(device,22,1);
       DrawCall draw=Get<DrawCall>(device,72);IntPtr vertices=Marshal.AllocHGlobal(48);
       Marshal.StructureToPtr(new Vertex(-0.8f,-0.8f,0xffff0000),vertices,false);Marshal.StructureToPtr(new Vertex(0,0.8f,0xff00ff00),IntPtr.Add(vertices,16),false);Marshal.StructureToPtr(new Vertex(0.8f,-0.8f,0xff0000ff),IntPtr.Add(vertices,32),false);
       for(int i=0;i<60;i++) {hr=clear(device,0,IntPtr.Zero,1,0xff183d63,1,0);if(hr<0)Marshal.ThrowExceptionForHR(hr);hr=begin(device);if(hr<0)Marshal.ThrowExceptionForHR(hr);hr=draw(device,4,1,vertices,16);if(hr<0)Marshal.ThrowExceptionForHR(hr);hr=end(device);if(hr<0)Marshal.ThrowExceptionForHR(hr);hr=present(device,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero);if(hr<0)Marshal.ThrowExceptionForHR(hr);Application.DoEvents();Thread.Sleep(20);}
       Marshal.FreeHGlobal(vertices);foreach(ProcessModule module in Process.GetCurrentProcess().Modules)if(module.ModuleName.ToLower().Contains("d3d"))Record("MODULE "+module.FileName);Record("HWND_CLIENT "+form.ClientSize.Width+"x"+form.ClientSize.Height);Record("PASS_CREATE_RENDER_PRESENT");result=0;
     }
   }catch(Exception error) {Record("FAIL "+error.ToString());}
   finally {
     try {
     if(targetsSlot!=IntPtr.Zero)Set(targetsSlot,Marshal.GetFunctionPointerForDelegate(targetsOriginal));if(textureSlot!=IntPtr.Zero)Set(textureSlot,Marshal.GetFunctionPointerForDelegate(textureOriginal));if(swapSlot!=IntPtr.Zero)Set(swapSlot,Marshal.GetFunctionPointerForDelegate(swapOriginal));if(hwndSlot!=IntPtr.Zero)Set(hwndSlot,Marshal.GetFunctionPointerForDelegate(hwndOriginal));
     if(surface!=IntPtr.Zero)Marshal.Release(surface);if(device!=IntPtr.Zero)Marshal.Release(device);if(d3d!=IntPtr.Zero)Marshal.Release(d3d);if(factory!=IntPtr.Zero)Marshal.Release(factory);if(context!=IntPtr.Zero)Marshal.Release(context);if(real!=IntPtr.Zero)Marshal.Release(real);
     MH_DisableHook(IntPtr.Zero);MH_Uninitialize();File.WriteAllLines(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"resolution-probe.txt"),output.ToArray());}catch(Exception cleanup){Record("CLEANUP_ERROR "+cleanup.ToString());result=2;}
   }
   return result;
 }
}
