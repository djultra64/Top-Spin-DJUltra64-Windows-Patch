"""Mouse/keyboard graphical launcher. Own work: djultra64."""
from pathlib import Path
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from launcher.process import run_game, save_configuration
from launcher.runtime import build_launch_plan, steam_locations, find_proton
from launcher.settings import Settings, RESOLUTIONS
from launcher.controllers import ACTIONS, NAMES
from launcher.steam import shortcut_spec, write_shortcut
from launcher.steam_client import discover_accounts, select_account, close_steam, reopen_steam, steam_is_running
from launcher.steam_artwork import install_artwork, validate_artwork
from launcher.integrity import verify_integrity


def show_launcher(game: Path,settings: Settings):
    window=tk.Tk();window.title('Top Spin Portable');window.geometry('700x700')
    window.minsize(650,600)
    style=ttk.Style(window)
    if 'clam' in style.theme_names():style.theme_use('clam')
    style.configure('Title.TLabel',font=('Sans',22,'bold'))
    style.configure('Sub.TLabel',foreground='#536273')
    main=ttk.Frame(window,padding=24);main.pack(fill='both',expand=True)
    header=tk.Frame(main,background='#0b242d');header.pack(fill='x',pady=(0,6))
    try:
        logo=tk.PhotoImage(file=str(game/'artwork/steam/logo-launcher.png'))
        tk.Label(header,image=logo,background='#0b242d').pack(anchor='w',padx=12,pady=8)
        window._topspin_logo=logo
    except (tk.TclError,OSError):
        tk.Label(header,text='TOP SPIN',font=('Sans',22,'bold'),foreground='white',
                 background='#0b242d').pack(anchor='w',padx=12,pady=8)
    try:
        icon=tk.PhotoImage(file=str(game/'artwork/steam/icon-launcher.png'))
        window.iconphoto(True,icon);window._topspin_icon=icon
    except (tk.TclError,OSError):pass
    ttk.Label(main,text='PORTABLE  ·  djultra64',style='Sub.TLabel').pack(anchor='w',pady=(0,18))
    actions=ttk.Frame(main);actions.pack(side='bottom',fill='x',pady=(12,0))
    pages=ttk.Notebook(main);pages.pack(fill='both',expand=True)
    graphics_page=ttk.Frame(pages,padding=8);pages.add(graphics_page,text='Graphics')
    control_page=ttk.Frame(pages,padding=14);pages.add(control_page,text='Controllers')
    form=ttk.LabelFrame(graphics_page,text='Graphics',padding=14);form.pack(fill='x')
    variables={name:tk.StringVar(value=getattr(settings,name))
               for name in ['internal_resolution','output_resolution','proton_dir']}
    toggles={name:tk.BooleanVar(value=getattr(settings,name))
             for name in ['fullscreen','frame_generation']}
    from launcher.windows_framegen import available as windows_framegen_available
    fg_available=sys.platform!='win32' or windows_framegen_available(game)
    if not fg_available:toggles['frame_generation'].set(False)
    for row,(name,label) in enumerate([('internal_resolution','Render resolution'),
                                       ('output_resolution','Display resolution')]):
        ttk.Label(form,text=label).grid(row=row,column=0,sticky='w',pady=5)
        ttk.Combobox(form,textvariable=variables[name],values=RESOLUTIONS,
                     state='readonly',width=22).grid(row=row,column=1,sticky='ew',padx=(24,0))
    form.columnconfigure(1,weight=1)
    ttk.Checkbutton(form,text='Full screen',variable=toggles['fullscreen']).grid(row=2,column=0,sticky='w',pady=8)
    fg=ttk.Checkbutton(form,text='Frame interpolation' if sys.platform=='win32' else 'Frame generation',variable=toggles['frame_generation'])
    fg.grid(row=2,column=1,sticky='w',padx=(24,0))
    if not fg_available:fg.state(['disabled'])
    ttk.Label(form,text='Original game speed: 50 FPS gameplay / 30 FPS replays.',
              style='Sub.TLabel').grid(row=3,column=0,columnspan=2,sticky='w',pady=(4,0))
    ttk.Label(form,text=('Windows frame interpolation component is not installed or needs repair.' if not fg_available else
                        'Frame interpolation adds smoothness without speeding up the game.'),
              style='Sub.TLabel').grid(row=4,column=0,columnspan=2,sticky='w')
    def update_proton_picker():
        if sys.platform!='linux':return
        try:
            available=find_proton(game,Settings(proton_dir=variables['proton_dir'].get()),dict(os.environ))
        except (OSError,ValueError):available=None
        if available:runtime.pack_forget()
        else:runtime.pack(fill='x',pady=14)
    if sys.platform=='linux':
        runtime=ttk.LabelFrame(graphics_page,text='Proton was not found automatically',padding=10)
        ttk.Label(runtime,text='Install Proton 11 in Steam, or choose its folder below.').pack(anchor='w')
        picker=ttk.Frame(runtime);picker.pack(fill='x',pady=(8,0))
        ttk.Label(picker,text='Proton folder').pack(side='left')
        ttk.Entry(picker,textvariable=variables['proton_dir']).pack(side='left',fill='x',expand=True,padx=12)
        def browse():
            folder=filedialog.askdirectory(title='Choose the Proton installation folder',parent=window)
            if folder:
                variables['proton_dir'].set(folder)
                update_proton_picker()
        ttk.Button(picker,text='Browse…',command=browse).pack(side='right')
        update_proton_picker()
    family_labels={'Keyboard':'keyboard','Auto detect (experimental)':'auto','Xbox 360':'xbox360','Xbox One / Xbox Series':'xbox',
                   'PlayStation 4':'ps4','PlayStation 5':'ps5','Nintendo Switch':'switch','Generic positions':'unknown'}
    family=tk.StringVar(value=next(label for label,key in family_labels.items() if key==settings.controller_family))
    ttk.Label(control_page,text='Controller button style').grid(row=0,column=0,sticky='w',pady=(0,10))
    family_box=ttk.Combobox(control_page,textvariable=family,values=tuple(family_labels),state='readonly',width=26)
    family_box.grid(row=0,column=1,sticky='ew',padx=(18,0),pady=(0,10))
    position_names=('South button','East button','West button','North button',
                    'Left shoulder','Right shoulder','Select / Back button','Start / Menu button')
    def labels_for_family():
        key=family_labels[family.get()]
        return tuple(label+' · '+name for label,name in zip(position_names,NAMES[key])) if key in NAMES else position_names
    physical_choices=[labels_for_family()]
    action_labels=('Primary / Accept','Secondary / Back','Third / Regenerate','Fourth / Help',
                   'Left shoulder action','Right shoulder action','Select / Back','Start / Pause')
    remaps=[];control_widgets=[family_box]
    ttk.Label(control_page,text='Button bindings · menus and gameplay',font=('Sans',11,'bold')).grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,6))
    for row,(action,label,position) in enumerate(zip(ACTIONS,action_labels,settings.menu_positions),2):
        variable=tk.StringVar(value=physical_choices[0][int(position)]);remaps.append(variable)
        ttk.Label(control_page,text=label).grid(row=row,column=0,sticky='w',pady=3)
        choice=ttk.Combobox(control_page,textvariable=variable,values=physical_choices[0],state='readonly',width=26)
        choice.grid(row=row,column=1,sticky='ew',padx=(18,0),pady=3);control_widgets.append(choice)
    def relabel_controls(event=None):
        selected=[physical_choices[0].index(variable.get()) for variable in remaps]
        physical_choices[0]=labels_for_family()
        for variable,widget,index in zip(remaps,control_widgets[1:],selected):
            widget.configure(values=physical_choices[0]);variable.set(physical_choices[0][index])
    family_box.bind('<<ComboboxSelected>>',relabel_controls)
    control_page.columnconfigure(1,weight=1)
    available=(game/'.portable/input.json').is_file()
    note=('Choose a button style to prepare fixed prompts before starting the game. Auto detect is experimental. '
          'Nintendo face-button positions are B / A / Y / X.' if available else
          'Controller options require the controller support package. Existing game controls remain available.')
    ttk.Label(control_page,text=note,wraplength=580,style='Sub.TLabel').grid(row=10,column=0,columnspan=2,sticky='w',pady=(12,0))
    if not available:
        for widget in control_widgets:widget.state(['disabled'])
    status=tk.StringVar(value='Portable graphics, display and controller settings.')
    ttk.Label(main,textvariable=status,wraplength=590,style='Sub.TLabel').pack(side='bottom',before=pages,fill='x',pady=(10,14))
    running=[False]
    def selection():
        return Settings(**{k:v.get() for k,v in variables.items()},**{k:v.get() for k,v in toggles.items()},
                        controller_family=family_labels[family.get()],
                        menu_positions=''.join(str(physical_choices[0].index(v.get())) for v in remaps))
    def save():
        try:save_configuration(game,selection());status.set('Settings saved in this portable folder.')
        except (OSError,ValueError) as exc:messagebox.showerror('Settings',str(exc),parent=window)
    def check():
        for button in buttons:button.state(['disabled'])
        status.set('Checking game files for integrity…')
        def checked(result,error):
            for button in buttons:button.state(['!disabled'])
            if error:status.set(str(error));return
            status.set(result.summary)
            if not result.ok:
                details=('Missing: '+', '.join(result.missing)+'\n' if result.missing else '')
                if result.modified:details+='Modified: '+', '.join(result.modified)
                messagebox.showwarning('Game file integrity',details,parent=window)
        def worker():
            result=None;error=None
            try:result=verify_integrity(game)
            except (OSError,ValueError) as exc:error=exc
            window.after(0,lambda:checked(result,error))
        threading.Thread(target=worker,daemon=False).start()
    def finished(result,error):
        running[0]=False
        for button in buttons:button.state(['!disabled'])
        window.deiconify()
        update_proton_picker()
        status.set('Game closed.' if result==0 else 'Game exited with code '+str(result)+'. See .portable/logs/launch.log.')
        if error:messagebox.showerror('Unable to start Top Spin',str(error),parent=window)
    def play():
        update_proton_picker()
        try:
            selected=selection();build_launch_plan(game,selected)
        except (OSError,ValueError) as exc:
            messagebox.showerror('Unable to start Top Spin',str(exc),parent=window);return
        running[0]=True
        for button in buttons:button.state(['disabled'])
        status.set('Top Spin is running.');window.iconify()
        def worker():
            result=None;error=None
            try:result=run_game(game,selected)
            except Exception as exc:error=exc
            window.after(0,lambda:finished(result,error))
        threading.Thread(target=worker,daemon=False).start()
    def add_to_steam():
        try:
            target=game/('TopSpinLauncher.exe' if sys.platform=='win32' else 'TopSpinLauncher.sh')
            if not target.is_file():raise ValueError('The packaged launcher entry point was not found.')
            if (game/'artwork/steam').is_dir():validate_artwork(game)
            accounts=discover_accounts(steam_locations(dict(os.environ),sys.platform))
            if not accounts:raise ValueError('No Steam user profile was found. Sign in to Steam once, then try again.')
            def install(account):
                try:save_configuration(game,selection())
                except (OSError,ValueError) as exc:
                    messagebox.showerror('Add to Steam',str(exc),parent=window);return
                running[0]=True
                for button in buttons:button.state(['disabled'])
                status.set('Adding Top Spin to Steam. Steam will close briefly if it is open…')
                def complete(message,error):
                    running[0]=False
                    for button in buttons:button.state(['!disabled'])
                    if window.state()=='iconic':window.deiconify()
                    status.set(message)
                    if error:messagebox.showerror('Add to Steam',str(error),parent=window)
                def worker():
                    error=None;message='Unable to add Top Spin to Steam.';closed=False
                    try:
                        closed=close_steam(account.steam_root)
                        appid=write_shortcut(account.shortcuts_path,shortcut_spec(game),
                                             steam_running=steam_is_running())
                        message='Top Spin added to Steam for '+account.display_name+'.'
                        if (game/'artwork/steam').is_dir():install_artwork(game,account.shortcuts_path,appid)
                    except (OSError,ValueError,subprocess.SubprocessError) as exc:error=exc
                    finally:
                        if closed:
                            try:reopen_steam(account.steam_root)
                            except (OSError,ValueError,subprocess.SubprocessError) as exc:
                                if error is None:error=exc
                        window.after(0,lambda:complete(message,error))
                threading.Thread(target=worker,daemon=False).start()
            account=select_account(accounts)
            if account is not None:
                install(account);return
            dialog=tk.Toplevel(window);dialog.title('Add to Steam');dialog.transient(window);dialog.grab_set()
            body=ttk.Frame(dialog,padding=18);body.pack(fill='both',expand=True)
            ttk.Label(body,text='Steam did not identify its most recent account. Choose one below.').pack(anchor='w')
            base_labels=[account.display_name+' · '+account.account_id for account in accounts]
            labels=[label+' · '+str(account.steam_root) if base_labels.count(label)>1 else label
                    for account,label in zip(accounts,base_labels)]
            choice=tk.StringVar(value=labels[0])
            account_box=ttk.Combobox(body,textvariable=choice,values=labels,state='readonly',width=66)
            account_box.pack(pady=12);account_box.current(0)
            def add():
                account=accounts[account_box.current()]
                dialog.destroy();install(account)
            ttk.Button(body,text='Add to Steam',command=add).pack(anchor='e',pady=(16,0))
        except (OSError,ValueError) as exc:messagebox.showerror('Add to Steam',str(exc),parent=window)
    buttons=[]
    for index,(label,action) in enumerate([('Play',play),('Save settings',save),('Check game files for integrity',check),('Add to Steam',add_to_steam)]):
        button=ttk.Button(actions,text=label,command=action)
        button.grid(row=index//2,column=index%2,sticky='ew',padx=(0,8),pady=3);buttons.append(button)
    for column in range(2):actions.columnconfigure(column,weight=1)
    def close():
        if running[0]:window.iconify()
        else:window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    window.mainloop();return 0
