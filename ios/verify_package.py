#!/usr/bin/env python3
"""Inspect a built IPA without claiming device runtime verification."""
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import sys
import zipfile

def verify(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, 'Corrupt ZIP entry'
        root = 'Payload/SuperTux.app/'
        info = plistlib.loads(archive.read(root + 'Info.plist'))
        assert info['MinimumOSVersion'] == '6.0'
        assert info.get('UIApplicationExitsOnSuspend') is False, 'App must support background/resume'
        assert info['CFBundleExecutable'] == 'SuperTux'
        assert info['CFBundleIdentifier'] == 'org.supertux.ios6'
        assert info['UIDeviceFamily'] == [1, 2]
        assert set(info['UISupportedInterfaceOrientations']) == {'UIInterfaceOrientationLandscapeLeft', 'UIInterfaceOrientationLandscapeRight'}
        binary = archive.read(root + 'SuperTux')
        magic, cpu, subtype, filetype, ncmds, sizeofcmds, flags = struct.unpack_from('<7I', binary)
        assert magic == 0xfeedface and cpu == 12 and subtype & 0xffffff == 9, 'Expected 32-bit ARMv7 Mach-O'
        assert filetype == 2, 'Expected executable'
        minimum = None
        signature = False
        libraries = []
        offset = 28
        for _ in range(ncmds):
            command, size = struct.unpack_from('<II', binary, offset)
            assert size >= 8 and offset + size <= 28 + sizeofcmds
            if command == 0x25:
                minimum, sdk = struct.unpack_from('<II', binary, offset + 8)
            if command in (0xc, 0x80000018):
                name_offset = struct.unpack_from('<I', binary, offset + 8)[0]
                name = binary[offset + name_offset:offset + size].split(b'\0')[0].decode()
                libraries.append(name)
                assert name.startswith(('/usr/lib/', '/System/Library/Frameworks/')), name
            if command == 0x1d:
                signature = True
            offset += size
        assert minimum == 0x00060000, 'Incorrect deployment target'
        assert signature, 'Missing ad hoc code signature'
        levels = sorted(name[len(root + 'data/'):] for name in archive.namelist() if name.startswith(root + 'data/') and name.endswith(('.stl', '.stwm')))
        original = Path(__file__).resolve().parent.parent / 'data'
        expected = sorted(p.relative_to(original).as_posix() for p in original.rglob('*') if p.is_file() and p.suffix in ('.stl', '.stwm'))
        assert levels == expected and len(levels) > 100
        for p in original.rglob('*'):
            if p.is_file():
                assert archive.read(root + 'data/' + p.relative_to(original).as_posix()) == p.read_bytes(), str(p)
        assert root + 'Default-568h@2x.png' in archive.namelist()
        for resource in ['images/tiles.strf', 'fonts/SuperTux-Medium.ttf', 'scripts/default.nut', 'images/engine/mobile/direction.png', 'music/antarctic/midday.music', 'music/antarctic/midday.ogg', 'music/misc/leveldone.ogg', 'LICENSE.txt']:
            assert root + 'data/' + resource in archive.namelist(), 'Missing ' + resource
        print(json.dumps({'ipa': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cpu': 'armv7', 'minimum_ios': '6.0', 'levels': levels, 'libraries': libraries, 'ad_hoc_signature': signature, 'device_tested': False}, indent=2))

if __name__ == '__main__':
    verify(Path(sys.argv[1]))
