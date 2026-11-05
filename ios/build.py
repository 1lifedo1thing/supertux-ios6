#!/usr/bin/env python
"""Build with the Apple compilers bundled in Xcode 6.2 (Python 2.7 compatible)."""
from __future__ import print_function
import glob
import hashlib
import json
import multiprocessing.pool
import os
import plistlib
import shutil
import subprocess
import sys
import zipfile
import tarfile
import gzip
import io
import time
import fcntl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
V = os.path.join(HERE, 'vendor')
G = os.path.join(HERE, 'generated')
B = os.path.join(HERE, 'build')
SDK = os.environ.get('IOS_SDK', subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path']).strip().decode('utf-8'))
ARCH = os.environ.get('IOS_ARCH', 'armv7')
MIN = os.environ.get('IOS_MIN', '6.0')
APP_VERSION = '0.10'
CC = subprocess.check_output(['xcrun', '--find', 'clang']).strip().decode('utf-8')
CXX = subprocess.check_output(['xcrun', '--find', 'clang++']).strip().decode('utf-8')

def mkdir(p):
    if not os.path.isdir(p):
        try:
            os.makedirs(p)
        except OSError:
            if not os.path.isdir(p):
                raise

def write(name, data):
    p = os.path.join(G, name)
    mkdir(os.path.dirname(p))
    if not os.path.isfile(p) or open(p).read() != data:
        with open(p, 'w') as f:
            f.write(data)

def files(base, patterns):
    return sorted(set(p for pattern in patterns.split() for p in glob.glob(os.path.join(base, pattern))))

def configure():
    mkdir(B)
    write('pnglibconf.h', open(os.path.join(V, 'png/scripts/pnglibconf.h.prebuilt')).read())
    write('ogg/config_types.h', '#pragma once\n#include <stdint.h>\ntypedef int16_t ogg_int16_t;\ntypedef uint16_t ogg_uint16_t;\ntypedef int32_t ogg_int32_t;\ntypedef uint32_t ogg_uint32_t;\ntypedef int64_t ogg_int64_t;\ntypedef uint64_t ogg_uint64_t;\n')
    modules = [('FT_Module_Class', 'autofit_module_class'), ('FT_Driver_ClassRec', 'tt_driver_class'), ('FT_Module_Class', 'sfnt_module_class'), ('FT_Module_Class', 'psnames_module_class'), ('FT_Renderer_Class', 'ft_raster1_renderer_class'), ('FT_Renderer_Class', 'ft_smooth_renderer_class')]
    write('freetype/config/ftmodule.h', ''.join('FT_USE_MODULE(%s, %s)\n' % pair for pair in modules))
    sdl_config = os.path.join(V, 'SDL/include/SDL_config_iphoneos.h')
    text = open(sdl_config).read()
    for feature in ['SDL_JOYSTICK_MFI', 'SDL_JOYSTICK_HIDAPI', 'SDL_SENSOR_COREMOTION', 'SDL_IPHONE_LAUNCHSCREEN']:
        import re
        text = re.sub(r'^#define ' + feature + r'.*$', '/* Disabled for iOS 6 prototype: ' + feature + ' */', text, flags=re.M)
    if '#define SDL_JOYSTICK_DUMMY 1' not in text:
        text = text.replace('#define SDL_HAPTIC_DUMMY 1', '#define SDL_HAPTIC_DUMMY 1\n#define SDL_JOYSTICK_DUMMY 1\n#define SDL_SENSOR_DUMMY 1')
    if open(sdl_config).read() != text:
        with open(sdl_config, 'w') as f:
            f.write(text)
    # SDL 2.0.12 contains runtime-guarded calls whose declarations are absent
    # in the 8.2 SDK. This prototype only runs on iOS 6, so use legacy paths.
    substitutions = {
        'src/audio/coreaudio/SDL_coreaudio.m': [('[session setCategory:category mode:mode options:options error:&err]', '[session setCategory:category error:&err]')],
        'src/video/uikit/SDL_uikitmessagebox.m': [('alert.preferredAction = action;', '/* iOS 6: no preferredAction API. */')],
        'src/video/uikit/SDL_uikitviewcontroller.m': [('[viewcontroller setNeedsUpdateOfHomeIndicatorAutoHidden];', '/* iOS 6 has no home indicator. */'), ('[viewcontroller setNeedsUpdateOfScreenEdgesDeferringSystemGestures];', '/* iOS 6 has no deferred system gestures. */')],
        'src/video/uikit/SDL_uikitappdelegate.m': [('/* exit(exit_status); */', 'exit(exit_status); /* SuperTux owns its native main loop. */')],
        'src/joystick/SDL_joystick.c': [('#if defined(__IPHONEOS__) || defined(__TVOS__)', '#if (defined(__IPHONEOS__) || defined(__TVOS__)) && !defined(SDL_JOYSTICK_DUMMY)')],
    }
    for relative, changes in substitutions.items():
        p = os.path.join(V, 'SDL', relative)
        original = open(p).read()
        patched = original
        for before, after in changes:
            patched = patched.replace(before, after)
        if original != patched:
            with open(p, 'w') as f:
                f.write(patched)
    p = os.path.join(V, 'SDL/src/video/uikit/SDL_uikitviewcontroller.m')
    text = open(p).read()
    before = '- (void)doLoop:(CADisplayLink*)sender\n{'
    after = before + '\n    /* SuperTux: never restore a GL context while inactive. */\n    if ([UIApplication sharedApplication].applicationState != UIApplicationStateActive) return;'
    if 'SuperTux: never restore' not in text:
        with open(p, 'w') as f: f.write(text.replace(before, after))
    p = os.path.join(V, 'SDL/src/video/uikit/SDL_uikitopengles.m')
    text = open(p).read()
    marker = '#endif /* SDL_VIDEO_DRIVER_UIKIT */'
    patch = '''
/* SuperTux: keep healthy foreground drawable storage and refresh only if lost. */
int SuperTux_UIKitRestoreDrawable(void)
{
    if ([UIApplication sharedApplication].applicationState != UIApplicationStateActive)
        return SDL_SetError("Cannot restore drawable while inactive");
    UIKit_GL_RestoreCurrentContext();
    SDLEAGLContext *context = (__bridge SDLEAGLContext *)SDL_GL_GetCurrentContext();
    if (!context || !context.sdlView) return SDL_SetError("Missing foreground drawable");
    GLint previousFramebuffer = 0;
    glGetIntegerv(GL_FRAMEBUFFER_BINDING, &previousFramebuffer);
    glBindFramebuffer(GL_FRAMEBUFFER, context.sdlView.drawableFramebuffer);
    if (context.sdlView.backingWidth <= 0 || context.sdlView.backingHeight <= 0 ||
        glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        [context.sdlView updateFrame];
    const GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    glBindFramebuffer(GL_FRAMEBUFFER, previousFramebuffer);
    if (status != GL_FRAMEBUFFER_COMPLETE) return SDL_SetError("Incomplete foreground drawable");
    return 0;
}

'''
    if 'int SuperTux_UIKitRestoreDrawable(void)' in text:
        import re
        updated = re.sub(r'/\* SuperTux: (?:refresh the EAGL|keep healthy)[\s\S]*?int SuperTux_UIKitRestoreDrawable\(void\)\n\{[\s\S]*?\n\}\n\n', lambda match: patch.lstrip('\n'), text, count=1)
    else:
        assert marker in text
        updated = text.replace(marker, patch + marker)
    if updated != text:
        with open(p, 'w') as f: f.write(updated)
    p = os.path.join(ROOT, 'external/simplesquirrel/include/simplesquirrel/binding.hpp')
    text = open(p).read()
    before = 'struct funcBinding<offset, SQInteger, DefaultArgumentsImpl<DefaultArgs...>, Args...> {'
    after = 'struct funcBinding<offset, SQInteger, DefaultArgumentsImpl<DefaultArgs...>, HSQUIRRELVM, Args...> {'
    updated = text.replace(before, after).replace('FuncPtr<SQInteger(Args...)>* funcPtr;', 'FuncPtr<SQInteger(HSQUIRRELVM, Args...)>* funcPtr;')
    if updated != text:
        with open(p, 'w') as f: f.write(updated)
    p = os.path.join(ROOT, 'external/sexp-cpp/src/float.cpp')
    original = open(p).read()
    text = original.replace('#include <charconv>', '// Xcode 6: unused C++17 charconv include omitted.')
    if text != original:
        with open(p, 'w') as f:
            f.write(text)
    p = os.path.join(V, 'filesystem/include/ghc/filesystem.hpp')
    original = open(p).read()
    text = original.replace('#elif defined(GHC_OS_MACOS) && \\', '#elif defined(SUPERTUX_IOS6) || defined(GHC_OS_MACOS) && \\')
    if text != original:
        with open(p, 'w') as f:
            f.write(text)

def groups():
    sdl = files(os.path.join(V, 'SDL'), '''src/*.c src/atomic/*.c src/audio/*.c src/audio/dummy/*.c src/audio/coreaudio/*.m src/cpuinfo/*.c src/dynapi/*.c src/events/*.c src/file/*.c src/haptic/*.c src/haptic/dummy/*.c src/joystick/*.c src/joystick/dummy/*.c src/libm/*.c src/loadso/dlopen/*.c src/power/*.c src/power/uikit/*.m src/render/*.c src/render/software/*.c src/render/opengles/*.c src/render/opengles2/*.c src/sensor/*.c src/sensor/dummy/*.c src/stdlib/*.c src/thread/*.c src/thread/pthread/*.c src/timer/*.c src/timer/unix/*.c src/video/*.c src/video/uikit/*.m src/video/uikit/*.c src/video/dummy/*.c src/filesystem/cocoa/*.m src/core/unix/*.c src/core/darwin/*.m''')
    sdl += files(os.path.join(V, 'SDL'), 'src/video/yuv2rgb/yuv_rgb.c src/file/cocoa/SDL_rwopsbundlesupport.m')
    yield 'SDL', sdl, [], []
    yield 'png', [p for p in files(os.path.join(V, 'png'), '*.c') if os.path.basename(p) != 'pngtest.c'], ['PNG_ARM_NEON_OPT=0'], []
    ft = 'src/base/ftbase.c src/base/ftbbox.c src/base/ftbitmap.c src/base/ftglyph.c src/base/ftinit.c src/base/ftstroke.c src/base/ftsynth.c src/base/ftsystem.c src/base/ftdebug.c src/autofit/autofit.c src/truetype/truetype.c src/sfnt/sfnt.c src/smooth/smooth.c src/raster/raster.c src/psnames/psnames.c src/gzip/ftgzip.c'
    yield 'freetype', files(os.path.join(V, 'freetype'), ft), ['FT2_BUILD_LIBRARY', 'FT_CONFIG_OPTION_SYSTEM_ZLIB'], []
    yield 'SDL_image', files(os.path.join(V, 'SDL_image'), 'IMG*.c'), ['LOAD_PNG', 'PNG_ARM_NEON_OPT=0', 'SDL_IMAGE_USE_COMMON_BACKEND=1'], []
    yield 'SDL_ttf', files(os.path.join(V, 'SDL_ttf'), 'SDL_ttf.c'), [], []
    yield 'ogg', files(os.path.join(V, 'ogg'), 'src/bitwise.c src/framing.c'), [], []
    vorbis = files(os.path.join(V, 'vorbis'), 'lib/*.c')
    vorbis = [p for p in vorbis if os.path.basename(p) not in ('barkmel.c', 'psytune.c', 'tone.c')]
    yield 'vorbis', vorbis, [], []
    yield 'physfs', files(os.path.join(V, 'physfs'), 'src/*.c src/physfs_platform_apple.m'), [], []
    yield 'sexp', files(os.path.join(ROOT, 'external/sexp-cpp'), 'src/*.cpp'), [], []
    yield 'tinygettext', files(os.path.join(ROOT, 'external/tinygettext'), 'src/*.cpp'), ['TINYGETTEXT_WITH_SDL', 'VERSION="0.2.0"'], []
    yield 'squirrel', files(os.path.join(ROOT, 'external/simplesquirrel/libs/squirrel'), 'squirrel/*.cpp sqstdlib/*.cpp'), [], []
    yield 'simplesquirrel', files(os.path.join(ROOT, 'external/simplesquirrel'), 'source/*.cpp'), [], []
    yield 'support', files(os.path.join(ROOT, 'external'), 'findlocale/findlocale.c obstack/obstack.c partio_zip/zip_manager.cpp SDL_SavePNG/savepng.c'), [], []
    yield 'port', files(HERE, 'port/*.m'), [], []
    source = files(os.path.join(G, 'src'), '*/*.cpp supertux/menu/*.cpp video/sdl/*.cpp video/null/*.cpp main.cpp')
    yield 'game', source, [], []

INCLUDES = [G, os.path.join(HERE, 'compat'), os.path.join(G, 'src')]
INCLUDES += [os.path.join(V, p) for p in ['SDL/include', 'SDL_image', 'SDL_ttf', 'freetype/include', 'png', 'ogg/include', 'vorbis/include', 'vorbis/lib', 'physfs/src', 'fmt/include', 'glm', 'optional-lite/include', 'variant-lite/include', 'string-view-lite/include', 'filesystem/include']]
INCLUDES += [os.path.join(ROOT, p) for p in ['external/sexp-cpp/include', 'external/tinygettext/include', 'external/simplesquirrel/include', 'external/simplesquirrel/libs/squirrel/include', 'external/obstack', 'external/findlocale', 'external/partio_zip', 'external/SDL_SavePNG']]
COMMON = ['-arch', ARCH, '-isysroot', SDK, '-miphoneos-version-min=' + MIN, '-O2', '-g', '-fvisibility=hidden', '-ffunction-sections', '-fdata-sections', '-DNDEBUG', '-DSUPERTUX_IOS6=1', '-DENABLE_TOUCHSCREEN_SUPPORT=1', '-DFMT_HEADER_ONLY=1', '-DGLM_ENABLE_EXPERIMENTAL', '-DGLM_FORCE_CTOR_INIT', '-Wno-deprecated-declarations', '-Wno-unused-command-line-argument']
COMMON += ['-I' + p for p in INCLUDES]
PCH = os.path.join(B, 'ios-prefix.pch')

def prepare_pch():
    headers = ['memory', 'algorithm', 'utility', 'type_traits', 'string', 'vector', 'map', 'unordered_map', 'functional', 'fstream', 'sstream', 'tuple', 'optional', 'variant', 'string_view', 'SDL.h', 'SDL_ttf.h', 'SDL_image.h', 'physfs.h', 'fmt/format.h', 'glm/glm.hpp']
    write('ios-prefix.hpp', '#include "' + os.path.join(HERE, 'compat/legacy.hpp') + '"\n' + ''.join('#include <' + h + '>\n' for h in headers))
    source = os.path.join(G, 'ios-prefix.hpp')
    command = [CXX] + COMMON + ['-std=c++1y', '-stdlib=libc++', '-x', 'c++-header', source, '-o', PCH]
    signature = hashlib.sha256((' '.join(command)).encode('utf-8')).hexdigest()
    stamp = PCH + '.command'
    if not os.path.isfile(PCH) or not os.path.isfile(stamp) or open(stamp).read() != signature or os.path.getmtime(source) > os.path.getmtime(PCH):
        subprocess.check_call(command)
        with open(stamp, 'w') as output:
            output.write(signature)

def compile_one(task):
    group, source, defines, extra = task
    digest = hashlib.sha1(source.encode('utf-8')).hexdigest()[:12]
    obj = os.path.join(B, group, os.path.basename(source) + '-' + digest + '.o')
    log = obj + '.log'
    mkdir(os.path.dirname(obj))
    cpp = source.endswith(('.cpp', '.mm'))
    command = [CXX if cpp else CC] + COMMON + ['-D' + d for d in defines] + extra
    if cpp:
        command += ['-std=c++1y', '-stdlib=libc++']
        command += ['-include-pch', PCH] if group == 'game' else ['-include', os.path.join(HERE, 'compat/legacy.hpp')]
    else:
        command += ['-std=gnu99']
    if source.endswith('.m'):
        command += ['-fobjc-arc'] if group == 'SDL' else ['-fno-objc-arc']
    command += ['-MMD', '-MF', obj + '.d', '-c', source, '-o', obj]
    signature = hashlib.sha256((' '.join(command)).encode('utf-8')).hexdigest()
    stamp = obj + '.command'
    if os.path.exists(obj) and os.path.exists(obj + '.d') and os.path.exists(stamp) and open(stamp).read() == signature:
        dependencies = open(obj + '.d').read().replace('\\\n', ' ').split(':', 1)[1].split()
        if group == 'game':
            dependencies.append(PCH)
        if all(os.path.exists(p) and os.path.getmtime(p) <= os.path.getmtime(obj) for p in dependencies):
            return obj, None
    with open(log, 'w') as output:
        result = subprocess.call(command, stdout=output, stderr=output)
    if result:
        return obj, open(log).read()
    with open(stamp, 'w') as output:
        output.write(signature)
    return obj, None

def debian_package(app):
    control = 'Package: org.supertux.ios6\nReplaces: org.supertux.ios6.prototype, com.alsainz.supertux\nConflicts: org.supertux.ios6.prototype, com.alsainz.supertux\nVersion: ' + APP_VERSION + '\nArchitecture: iphoneos-arm\nMaintainer: Local build\nSection: Games\nPriority: optional\nDepends: firmware (>= 6.0)\nName: SuperTux\nDescription: SuperTux 0.7.0 full bundled game with touch controls.\n'
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, content, mode in [('control', control, 0o644), ('postinst', '#!/bin/sh\nif command -v uicache >/dev/null 2>&1; then uicache >/dev/null 2>&1 || true; fi\nexit 0\n', 0o755)]:
            payload = content.encode('utf-8')
            info = tarfile.TarInfo('./' + name)
            info.size = len(payload)
            info.mode = mode
            archive.addfile(info, io.BytesIO(payload))
    control_data = buffer.getvalue()
    buffer = io.BytesIO()
    def ownership(info):
        info.uid = info.gid = 0
        info.uname = info.gname = 'root'
        return info
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        archive.add(app, arcname='./Applications/SuperTux.app', filter=ownership)
    deb = os.path.join(B, 'org.supertux.ios6_' + APP_VERSION + '_iphoneos-arm.deb')
    with open(deb, 'wb') as output:
        output.write(b'!<arch>\n')
        for name, payload in [('debian-binary', b'2.0\n'), ('control.tar.gz', control_data), ('data.tar.gz', buffer.getvalue())]:
            header = '%-16s%-12d%-6d%-6d%-8s%-10d`\n' % (name + '/', int(time.time()), 0, 0, '100644', len(payload))
            output.write(header.encode('ascii'))
            output.write(payload)
            if len(payload) % 2:
                output.write(b'\n')
    print('Built:', deb)

def main():
    mkdir(B)
    build_lock = open(os.path.join(B, 'build.lock'), 'w')
    try:
        fcntl.flock(build_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        raise RuntimeError('Another SuperTux iOS build is already running')
    configure()
    tasks = [(name, p, defines, extra) for name, sources, defines, extra in groups() for p in sources]
    if '--group' in sys.argv:
        selected = sys.argv[sys.argv.index('--group') + 1].split(',')
        tasks = [t for t in tasks if t[0] in selected]
    if '--filter' in sys.argv:
        needle = sys.argv[sys.argv.index('--filter') + 1]
        tasks = [t for t in tasks if needle in t[1]]
        if not tasks:
            raise RuntimeError('No translation units match ' + needle)
    if any(t[0] == 'game' for t in tasks):
        prepare_pch()
    print('Xcode compiler:', subprocess.check_output([CC, '--version']).decode('utf-8').splitlines()[0])
    print('Target:', ARCH, 'iOS', MIN, 'SDK:', SDK)
    print('Checking', len(tasks), 'translation units')
    sys.stdout.flush()
    pool = multiprocessing.pool.ThreadPool(int(os.environ.get('JOBS', '4')))
    errors = []
    objects = []
    for i, (obj, error) in enumerate(pool.imap(compile_one, tasks)):
        objects.append(obj)
        if error:
            errors.append((obj, error))
            print('FAILED:', os.path.basename(obj))
        if (i + 1) % 50 == 0:
            print('Checked %d/%d units; %d failures' % (i + 1, len(tasks), len(errors)))
            sys.stdout.flush()
    pool.close()
    pool.join()
    with open(os.path.join(B, 'errors.log'), 'w') as output:
        for obj, error in errors:
            output.write('\n' + obj + '\n' + error)
    if errors:
        print('Build failed:', len(errors), 'units. See ios/build/errors.log')
        print(errors[0][1][:5000])
        return 1
    if '--group' in sys.argv:
        print('Selected dependency groups compiled successfully.')
        return 0
    # The C++14 port defines the shared colors in one translation unit.
    # Place its initializer before translation units that can copy those values.
    objects.sort(key=lambda p: (0 if 'ios_color_constants.cpp-' in p else 1, p))
    app = os.path.join(B, 'Payload/SuperTux.app')
    mkdir(app)
    binary = os.path.join(app, 'SuperTux')
    frameworks = ['CoreText', 'UIKit', 'Foundation', 'QuartzCore', 'OpenGLES', 'OpenAL', 'AudioToolbox', 'CoreAudio', 'CoreGraphics', 'CoreMotion', 'AVFoundation']
    command = [CXX, '-arch', ARCH, '-isysroot', SDK, '-miphoneos-version-min=' + MIN, '-stdlib=libc++', '-Wl,-dead_strip', '-o', binary] + objects + ['-lz', '-liconv']
    for framework in frameworks:
        command += ['-framework', framework]
    subprocess.check_call(command)
    shutil.copy2(os.path.join(HERE, 'Info.plist'), os.path.join(app, 'Info.plist'))
    data = os.path.join(HERE, 'Resources/data')
    if not os.path.isdir(data):
        raise RuntimeError('Run ios/package_data.py on the preparation host first')
    assert os.path.realpath(app).startswith(os.path.realpath(B) + os.sep)
    subprocess.check_call(['rsync', '-a', '--delete', data + '/', os.path.join(app, 'data/')])
    for icon in glob.glob(os.path.join(HERE, 'Resources/*.png')):
        shutil.copy2(icon, app)
    for folder, dirs, names in os.walk(app):
        os.chmod(folder, 0o755)
        for name in names:
            os.chmod(os.path.join(folder, name), 0o755 if name == 'SuperTux' else 0o644)
    subprocess.check_call(['codesign', '--force', '--sign', '-', app])
    ipa = os.path.join(B, 'SuperTux-0.7.0-iOS6-' + APP_VERSION + '.ipa')
    with zipfile.ZipFile(ipa, 'w', zipfile.ZIP_DEFLATED) as output:
        for base, dirs, names in os.walk(os.path.join(B, 'Payload')):
            for name in names:
                p = os.path.join(base, name)
                output.write(p, os.path.relpath(p, B))
    print('Built:', ipa)
    debian_package(app)
    return 0

if __name__ == '__main__':
    sys.exit(main())
