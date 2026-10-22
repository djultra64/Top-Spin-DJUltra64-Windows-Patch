"""Responsive Linux ISO setup and headless CLI. Own work: djultra64."""
from __future__ import annotations

import argparse
from pathlib import Path
import queue
import subprocess
import sys
import threading


def _install_from_iso(iso, destination, payload, *, progress, cancel):
    from tools.iso_install import install_from_iso
    return install_from_iso(iso, destination, payload, progress=progress, cancel=cancel)


def default_destination():
    return Path.home()/'Games'/'Top Spin'


def destination_in_parent(parent):
    return Path(parent).expanduser()/'Top Spin'


def installation_paths(iso, destination):
    if not str(iso).strip():
        raise ValueError('Choose a game ISO file.')
    if not str(destination).strip():
        raise ValueError('Choose a new installation folder.')
    source = Path(iso).expanduser().absolute()
    target = Path(destination).expanduser().absolute()
    if not source.is_file():
        raise ValueError('The selected game ISO file was not found.')
    if target.exists() or target.is_symlink():
        raise ValueError('The installation folder already exists. Choose a new folder; existing folders are never overwritten.')
    return source, target


class InstallController:
    """Queue worker messages; only the caller draining them updates UI state."""
    def __init__(self, payload, *, install=None):
        self.payload = Path(payload).expanduser().absolute()
        self.install = install or _install_from_iso
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.succeeded = False
        self.destination = None

    def start(self, iso, destination):
        if self.running:
            raise ValueError('Installation is already running.')
        source, target = installation_paths(iso, destination)
        self.cancel = threading.Event()
        self.destination = target
        self.succeeded = False
        self.running = True
        def worker():
            try:
                result = self.install(source, target, self.payload,
                    progress=lambda message: self.events.put(('progress', str(message))),
                    cancel=self.cancel)
            except InterruptedError as exc:
                self.events.put(('cancelled', str(exc) or 'Installation cancelled.'))
            except Exception as exc:
                self.events.put(('error', str(exc) or type(exc).__name__))
            else:
                self.events.put(('success', result))
        try:
            threading.Thread(target=worker, name='TopSpinSetup', daemon=False).start()
        except Exception:
            self.running = False
            raise

    def request_cancel(self):
        if self.running:
            self.cancel.set()

    def drain(self):
        messages = []
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in ('success', 'error', 'cancelled'):
                self.running = False
                self.succeeded = kind == 'success'
            messages.append((kind, value))
        return messages


def show_setup(payload):
    # Tk must remain optional for --iso/--destination and --help.
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    window = tk.Tk()
    window.title('Top Spin Setup')
    window.geometry('740x620')
    window.minsize(660, 540)
    style = ttk.Style(window)
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    style.configure('Title.TLabel', font=('Sans', 22, 'bold'))
    style.configure('Sub.TLabel', foreground='#536273')
    main = ttk.Frame(window, padding=24)
    main.pack(fill='both', expand=True)
    ttk.Label(main, text='Top Spin Setup', style='Title.TLabel').pack(anchor='w')
    ttk.Label(main, text='Linux / Proton · djultra64', style='Sub.TLabel').pack(anchor='w', pady=(2, 14))
    ttk.Label(main, text='Choose your game ISO and a new installation folder. Setup extracts the game and applies the patch.',
              wraplength=650).pack(anchor='w', pady=(0, 16))
    controller = InstallController(payload)
    iso = tk.StringVar()
    destination = tk.StringVar(value=str(default_destination()))
    status = tk.StringVar(value='Choose a game ISO to begin.')
    form = ttk.Frame(main)
    form.pack(fill='x')
    form.columnconfigure(1, weight=1)
    controls = []

    def browse_iso():
        selected = filedialog.askopenfilename(parent=window, title='Choose your Top Spin game ISO',
                    filetypes=[('ISO images', '*.iso *.ISO'), ('All files', '*')])
        if selected:
            iso.set(selected)

    def browse_destination():
        selected = filedialog.askdirectory(parent=window, title='Choose a parent folder for Top Spin', mustexist=True)
        if selected:
            destination.set(str(destination_in_parent(selected)))

    for row, (label, variable, browse) in enumerate([
            ('Game ISO', iso, browse_iso), ('Install location', destination, browse_destination)]):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=7)
        entry = ttk.Entry(form, textvariable=variable)
        entry.grid(row=row, column=1, sticky='ew', padx=12, pady=7)
        button = ttk.Button(form, text='Browse…', command=browse)
        button.grid(row=row, column=2, pady=7)
        controls.extend([entry, button])
    ttk.Label(main, text='Browse selects a parent folder and adds “Top Spin”. You can type a different new folder. Existing folders are never overwritten.',
              style='Sub.TLabel', wraplength=650).pack(anchor='w', pady=(8, 14))
    progress = ttk.Progressbar(main, mode='indeterminate')
    progress.pack(fill='x', pady=(0, 10))
    ttk.Label(main, textvariable=status, wraplength=650).pack(anchor='w', pady=(0, 10))
    details = ttk.LabelFrame(main, text='Details', padding=8)
    details.pack(fill='both', expand=True)
    log = tk.Text(details, height=8, wrap='word', state='disabled', font=('Sans', 10))
    scrollbar = ttk.Scrollbar(details, command=log.yview)
    log.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    log.pack(fill='both', expand=True)
    actions = ttk.Frame(main)
    # Reserve the action row before the expandable log requests its space.
    actions.pack(side='bottom', fill='x', pady=(16, 0), before=details)
    close_requested = False

    def append(message):
        log.configure(state='normal')
        log.insert('end', str(message)+'\n')
        log.see('end')
        log.configure(state='disabled')

    def state(running):
        for widget in controls+[install_button]:
            widget.state(['disabled'] if running else ['!disabled'])
        cancel_button.configure(text='Cancel' if running else 'Done')
        cancel_button.state(['!disabled'])
        if running:
            progress.start(12)
        else:
            progress.stop()

    def begin():
        try:
            controller.start(iso.get(), destination.get())
        except (OSError, ValueError) as exc:
            status.set(str(exc))
            messagebox.showerror('Unable to install', str(exc), parent=window)
            return
        configurator.state(['disabled'])
        folder_button.state(['disabled'])
        state(True)
        status.set('Preparing installation…')
        append('Installing into '+str(controller.destination))

    def cancel_or_done():
        if controller.running:
            controller.request_cancel()
            status.set('Cancelling… waiting for temporary files to be cleaned up.')
            cancel_button.state(['disabled'])
        else:
            window.destroy()

    def close():
        nonlocal close_requested
        if not controller.running:
            window.destroy()
        elif messagebox.askyesno('Cancel installation?',
                'Cancel installation and close setup after temporary files are cleaned up?', parent=window):
            close_requested = True
            cancel_or_done()

    def open_configurator():
        try:
            target = controller.destination
            subprocess.Popen([str(target/'TopSpinLauncher.sh')], cwd=target)
        except OSError as exc:
            messagebox.showerror('Unable to open configurator', str(exc), parent=window)

    def open_folder():
        try:
            subprocess.Popen(['xdg-open', str(controller.destination)], cwd=controller.destination)
        except OSError as exc:
            messagebox.showerror('Unable to open folder', str(exc), parent=window)

    configurator = ttk.Button(actions, text='Open configurator', command=open_configurator)
    configurator.pack(side='left')
    configurator.state(['disabled'])
    folder_button = ttk.Button(actions, text='Open game folder', command=open_folder)
    folder_button.pack(side='left', padx=8)
    folder_button.state(['disabled'])
    cancel_button = ttk.Button(actions, text='Done', command=cancel_or_done)
    cancel_button.pack(side='right')
    install_button = ttk.Button(actions, text='Install', command=begin)
    install_button.pack(side='right', padx=8)

    def poll():
        for kind, value in controller.drain():
            if kind == 'progress':
                status.set(value)
                append(value)
            else:
                state(False)
                if kind == 'success':
                    status.set('Installation complete. Open the configurator when you are ready.')
                    configurator.state(['!disabled'])
                    folder_button.state(['!disabled'])
                    install_button.state(['disabled'])
                elif kind == 'cancelled':
                    status.set('Installation cancelled. No game was started.')
                else:
                    status.set('Installation failed: '+value)
                append(status.get())
                if close_requested:
                    window.destroy()
                    return
        window.after(80, poll)

    window.protocol('WM_DELETE_WINDOW', close)
    window.after(80, poll)
    window.mainloop()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install Top Spin from your own compatible ISO on Linux.')
    parser.add_argument('--iso', help='Your game ISO; use with --destination for headless installation')
    parser.add_argument('--destination', help='New game folder; existing folders are never overwritten')
    parser.add_argument('--payload', type=Path, default=Path.cwd()/'.topspin-patch', help='Bundled patch payload folder')
    arguments = parser.parse_args(argv)
    if (arguments.iso is None) != (arguments.destination is None):
        parser.error('--iso and --destination must be supplied together')
    if arguments.iso is None:
        try:
            return show_setup(arguments.payload)
        except Exception as exc:
            print('Unable to open Top Spin Setup: '+str(exc), file=sys.stderr)
            print('Use --iso and --destination for installation without a graphical display.', file=sys.stderr)
            return 1
    cancel = threading.Event()
    try:
        iso, destination = installation_paths(arguments.iso, arguments.destination)
        _install_from_iso(iso, destination, arguments.payload.expanduser().absolute(),
                          progress=lambda message: print(str(message), flush=True), cancel=cancel)
    except KeyboardInterrupt:
        cancel.set()
        print('Installation cancelled.', file=sys.stderr)
        return 130
    except Exception as exc:
        print('Installation failed: '+str(exc), file=sys.stderr)
        return 1
    print('Installation complete: '+str(destination))
    print('Open '+str(destination/'TopSpinLauncher.sh')+' to configure the game.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
