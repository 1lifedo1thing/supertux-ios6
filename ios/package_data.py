#!/usr/bin/env python3
"""Stage the full game data, icons and dependency attribution."""
from pathlib import Path
import hashlib
import json
import re
import shutil
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / 'data'
DEST = HERE / 'Resources/data'

def copy(relative):
    source = SOURCE / relative
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

def main():
    # Ship upstream data intact: title/intro, worlds, levels, music and locale.
    DEST.mkdir(parents=True, exist_ok=True)
    expected = {p.relative_to(SOURCE) for p in SOURCE.rglob('*') if p.is_file()}
    assert DEST.resolve().is_relative_to(HERE.resolve())
    for p in DEST.rglob('*'):
        if p.is_file() and p.relative_to(DEST) not in expected:
            assert p.resolve().is_relative_to(DEST.resolve())
            p.unlink()
    for relative in sorted(expected):
        copy(relative)
    # iOS 6 enables the 568-point iPhone/iPod display only with this launch image.
    Image.new('RGB', (640, 1136), (0, 0, 0)).save(HERE / 'Resources/Default-568h@2x.png')
    (DEST / 'LICENSE.txt').write_bytes((ROOT / 'LICENSE.txt').read_bytes())
    licenses = DEST / 'licenses'
    licenses.mkdir(exist_ok=True)
    for base in [HERE / 'vendor', ROOT / 'external']:
        for dependency in base.iterdir():
            if not dependency.is_dir():
                continue
            for p in dependency.iterdir():
                if p.is_file() and any(token in p.name.upper() for token in ['LICENSE', 'COPYING']):
                    shutil.copy2(p, licenses / (dependency.name + '-' + p.name))
    for name, size in [('Icon.png', 57), ('Icon@2x.png', 114), ('Icon-72.png', 72), ('Icon-72@2x.png', 144)]:
        with Image.open(SOURCE / 'images/engine/icons/supertux-256x256.png') as icon:
            icon.convert('RGB').resize((size, size), Image.Resampling.LANCZOS).save(HERE / 'Resources' / name)
    manifest = []
    for p in sorted(DEST.rglob('*')):
        if p.is_file():
            manifest.append({'path': p.relative_to(DEST).as_posix(), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    levels = [entry['path'] for entry in manifest if entry['path'].endswith(('.stl', '.stwm'))]
    assert 'levels/world1/welcome_antarctica.stl' in levels and len(levels) > 100
    (HERE / 'data-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Staged %d files, %.1f MiB; full game.' % (len(manifest), sum(e['bytes'] for e in manifest) / 1048576))

if __name__ == '__main__':
    main()
