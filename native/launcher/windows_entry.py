"""Frozen Windows launcher entry, containing only project code. djultra64."""
import json
from pathlib import Path
import sys

from launcher.__main__ import main


def verify_files(destination: Path, *, root: Path | None = None):
    """Read package checksums through the frozen executable, without a game run."""
    from launcher.integrity import verify_integrity
    root=root or Path(sys.executable).resolve().parent
    try:
        result=verify_integrity(root)
        report={'ok':result.ok,'summary':result.summary,'count':result.checked,
                'missing':list(result.missing),'modified':list(result.modified)}
    except (OSError,ValueError) as exc:
        report={'ok':False,'summary':str(exc),'count':0,'missing':[],'modified':[]}
    destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['ok'] else 1


def self_test(destination: Path):
    """Validate frozen Python/Tk in a real Windows process without starting a game."""
    import tkinter
    from launcher.controllers import FAMILIES
    from launcher.process import clean_windows_dll_search
    from launcher.runtime import build_launch_plan
    from launcher.settings import Settings
    from launcher.glyphs import FAMILIES as PROMPT_FAMILIES, plan_prompt_style
    from tools.controller_config import remap_existing_menu
    window = tkinter.Tk()
    window.withdraw()
    window.update_idletasks()
    result = {'ready': True, 'frozen': bool(getattr(sys, 'frozen', False)),
              'executable': str(Path(sys.executable).resolve()),
              'python': sys.version, 'tcl': window.tk.call('info', 'patchlevel'),
              'tk': window.tk.call('package', 'provide', 'Tk'),
              'controller_families': list(FAMILIES)}
    Settings(controller_family='keyboard')
    result['manual_prompt_families']=['keyboard']+list(PROMPT_FAMILIES)
    with clean_windows_dll_search():
        pass
    window.destroy()
    destination.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    # A windowed frozen executable has no console streams. File-based diagnostics
    # remain reviewable over SSH and do not open a game or modify its settings.
    if len(sys.argv) == 3 and sys.argv[1] == '--verify-files':
        sys.exit(verify_files(Path(sys.argv[2])))
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        try:
            sys.exit(self_test(Path(sys.argv[2])))
        except Exception as exc:
            Path(sys.argv[2]).write_text(json.dumps({'ready': False, 'error': str(exc)}), encoding='utf-8')
            sys.exit(1)
    sys.exit(main())
