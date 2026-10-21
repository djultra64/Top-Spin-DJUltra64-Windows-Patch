"""Build the tiny Windows direct-play entry point (own work: djultra64)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


def build_direct_entry(destination: Path, *, compiler: Path | None = None) -> Path:
    if os.name != "nt":
        raise RuntimeError("Compile this entry point on Windows using .NET Framework csc.exe.")
    source = Path(__file__).resolve().parents[1] / "native" / "launcher" / "PlayTopSpin.cs"
    if compiler is None:
        compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe"
    if not compiler.is_file():
        raise FileNotFoundError(f".NET Framework C# compiler not found: {compiler}")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "Play-TopSpin.exe"
    subprocess.run([str(compiler), "/nologo", "/target:winexe", "/platform:anycpu",
                    "/optimize+", "/reference:System.Windows.Forms.dll",
                    f"/out:{output.resolve()}", str(source)], check=True)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Windows direct-play entry point.")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--compiler", type=Path)
    options = parser.parse_args()
    print(build_direct_entry(options.destination, compiler=options.compiler))


if __name__ == "__main__":
    main()
