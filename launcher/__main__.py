"""English launcher entry point. Own work: djultra64."""
import argparse
import json
from pathlib import Path
import sys
from launcher.runtime import build_launch_plan
from launcher.settings import load_settings


def main():
    parser=argparse.ArgumentParser(description='Top Spin Portable Launcher')
    parser.add_argument('--game-dir',type=Path)
    parser.add_argument('--play',action='store_true',help='Start using saved launcher settings')
    parser.add_argument('--diagnose',action='store_true',help='Check dependencies without starting the game')
    args=parser.parse_args()
    root=(args.game_dir or (Path(sys.executable).parent if getattr(sys,'frozen',False)
                           else Path(__file__).resolve().parent.parent)).resolve()
    try:
        settings=load_settings(root)
        if args.diagnose:
            plan=build_launch_plan(root,settings)
            print(json.dumps({'ready':True,'command':plan.argv,'working_directory':str(plan.cwd)},indent=2))
            return 0
        if args.play:
            from launcher.process import run_game
            return run_game(root,settings)
        from launcher.gui import show_launcher
        return show_launcher(root,settings)
    except (OSError,ValueError,ImportError) as exc:
        print('Top Spin Portable: '+str(exc),file=sys.stderr)
        if not args.diagnose:
            try:
                from tkinter import Tk,messagebox
                window=Tk();window.withdraw()
                messagebox.showerror('Top Spin Portable',str(exc));window.destroy()
            except Exception:pass
        return 1

if __name__=='__main__':sys.exit(main())
