"""Build an explicit deployment archive that never includes local credentials/data."""
import hashlib
import tarfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
destination=root/'data/oracle-release.tar.gz'
destination.parent.mkdir(exist_ok=True)
allowed=['backend','deploy','frontend/dist','scripts/start.sh','schema.sql']
with tarfile.open(destination,'w:gz') as archive:
    for entry in allowed:
        path=root/entry
        files=sorted(path.rglob('*')) if path.is_dir() else [path]
        for file in files:
            if not file.is_file() or file.is_symlink(): continue
            relative=file.relative_to(root)
            if any(part in ('__pycache__','.pytest_cache','.secrets','.git') for part in relative.parts): continue
            if file.suffix in ('.pyc','.key','.pem') or file.name in ('.env','.env.live'): continue
            archive.add(file,arcname=relative.as_posix(),recursive=False)
print(str(destination))
print('sha256='+hashlib.sha256(destination.read_bytes()).hexdigest())
