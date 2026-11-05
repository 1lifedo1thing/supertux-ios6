#!/usr/bin/env python3
"""Fetch pinned source dependencies; run on the Windows preparation host."""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'vendor'
PACKAGES = {
    'SDL': ('https://www.libsdl.org/release/SDL2-2.0.12.tar.gz', '2.0.12'),
    'SDL_image': ('https://www.libsdl.org/projects/SDL_image/release/SDL2_image-2.0.5.tar.gz', '2.0.5'),
    'SDL_ttf': ('https://www.libsdl.org/projects/SDL_ttf/release/SDL2_ttf-2.0.15.tar.gz', '2.0.15'),
    'freetype': ('https://download.savannah.gnu.org/releases/freetype/freetype-2.10.4.tar.gz', '2.10.4'),
    'png': ('https://codeload.github.com/pnggroup/libpng/tar.gz/refs/tags/v1.6.37', '1.6.37'),
    'physfs': ('https://codeload.github.com/icculus/physfs/tar.gz/refs/tags/release-3.0.2', '3.0.2'),
    'fmt': ('https://codeload.github.com/fmtlib/fmt/tar.gz/refs/tags/7.1.3', '7.1.3'),
    'glm': ('https://codeload.github.com/g-truc/glm/tar.gz/refs/tags/0.9.9.8', '0.9.9.8'),
    'ogg': ('https://downloads.xiph.org/releases/ogg/libogg-1.3.5.tar.gz', '1.3.5'),
    'vorbis': ('https://downloads.xiph.org/releases/vorbis/libvorbis-1.3.7.tar.gz', '1.3.7'),
    'optional-lite': ('https://codeload.github.com/martinmoene/optional-lite/tar.gz/refs/tags/v3.6.0', '3.6.0'),
    'variant-lite': ('https://codeload.github.com/martinmoene/variant-lite/tar.gz/refs/tags/v2.0.0', '2.0.0'),
    'string-view-lite': ('https://codeload.github.com/martinmoene/string-view-lite/tar.gz/refs/tags/v1.6.0', '1.6.0'),
    'filesystem': ('https://codeload.github.com/gulrak/filesystem/tar.gz/refs/tags/v1.5.14', '1.5.14'),
}

def fetch(item):
    name, (url, version) = item
    dest = VENDOR / name
    marker = dest / '.download.json'
    if marker.exists():
        return name, json.loads(marker.read_text())
    payload = urllib.request.urlopen(url, timeout=120).read()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        members = archive.getmembers()
        prefix = members[0].name.split('/')[0] + '/'
        for member in members:
            relative = member.name.removeprefix(prefix)
            if not relative or relative == members[0].name or member.issym() or member.islnk():
                continue
            target = (dest / relative).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError('Unsafe archive path')
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode)
    record = {'url': url, 'version': version, 'sha256': hashlib.sha256(payload).hexdigest()}
    marker.write_text(json.dumps(record, indent=2) + '\n')
    print('Fetched ' + name, flush=True)
    return name, record

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = dict(pool.map(fetch, PACKAGES.items()))
    (ROOT / 'dependencies.lock.json').write_text(json.dumps(records, indent=2) + '\n')
