"""Install verified runtimes under the project; does not replace system Python."""
import hashlib
import json
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.runtime'
CACHE = ROOT / 'data/runtime-downloads'
RELEASES = {
    'python': (
        'https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.13.15%2B20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz',
        '8a689a077337bea6d1c4bc0b7df1d52fcaa28f5f67e50df8bf417c1e3f9d8874',
    ),
    'caddy': (
        'https://github.com/caddyserver/caddy/releases/download/v2.11.4/caddy_2.11.4_linux_amd64.tar.gz',
        '527fbf917c39189a1e3b31d34fa955601680b2d5c8055d2a87b8b9588dec7bb9',
    ),
}

def main():
    RUNTIME.mkdir(exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in RELEASES.items():
        archive = CACHE / (name + '.tar.gz')
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=45) as response, archive.open('wb') as output:
                shutil.copyfileobj(response, output)
        checksum = hashlib.sha256()
        with archive.open('rb') as content:
            for block in iter(lambda: content.read(1024 * 1024), b''): checksum.update(block)
        if checksum.hexdigest() != expected: raise RuntimeError(name + ' checksum mismatch; refusing to install')
        with tarfile.open(archive) as content:
            if name == 'python':
                if not hasattr(tarfile, 'data_filter'): raise RuntimeError('This Python needs the safe tar extraction backport')
                content.extractall(RUNTIME, filter='data')
            else:
                member = content.getmember('caddy')
                if not member.isfile(): raise RuntimeError('Unexpected Caddy archive layout')
                with content.extractfile(member) as source, (RUNTIME / 'caddy').open('wb') as output:
                    shutil.copyfileobj(source, output)
                (RUNTIME / 'caddy').chmod(0o755)
        print('Verified and installed ' + name, flush=True)

if __name__ == '__main__': main()
