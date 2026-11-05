# iOS 6 port

Current port build: 0.10. Bundle/package identifier: org.supertux.ios6.
Home Screen label: SuperTux. Target: ARMv7, minimum iOS 6.0.

## Prepare sources and assets

Use Python 3.10 or newer on a preparation computer. The preparation scripts do
not run under Mavericks' built-in Python 2.7.

```sh
python3 -m pip install -r ios/requirements.txt
python3 ios/fetch_dependencies.py
python3 ios/prepare_port.py
python3 ios/package_data.py
```

These commands recreate ios/vendor/, ios/generated/ and ios/Resources/.
External sources (including simplesquirrel/libs/squirrel) are included in this
snapshot. ios/submodules.lock.json records selected upstream revisions;
ios/dependencies.lock.json records downloaded versions and archive hashes.
Keep src/, data/, external/ and ios/ together when copying to the build Mac.

## Build on Mavericks with Xcode 6.2

Open ios/SuperTuxIOS.xcodeproj, or run from the project root:

```sh
xcodebuild -project ios/SuperTuxIOS.xcodeproj -target SuperTuxIOS -configuration Release
```

The legacy target invokes /usr/bin/python and ios/build.py. That script supports
Python 2.7 and uses Xcode's Apple compiler, iPhoneOS8.2 SDK and iOS 6 deployment
target. It applies the legacy SDL and 32-bit scripting compatibility patches.
For a different checkout location, no machine-specific SSH helper is needed.

Outputs:

- ios/build/SuperTux-0.7.0-iOS6-0.10.ipa
- ios/build/org.supertux.ios6_0.10_iphoneos-arm.deb

Packages are ad hoc signed for jailbreak installation. The DEB installs to
/Applications/SuperTux.app and replaces earlier prototype package identifiers.
Generated folders and binary packages are excluded from Git.

## Verify a package

On the preparation computer:

```sh
python3 ios/verify_package.py ios/build/SuperTux-0.7.0-iOS6-0.10.ipa
```

This checks the executable architecture, deployment target, identifier, archive
integrity and original game data. Native regression sources are in ios/tests/.
The one-time run_script_binding.sh diagnostic expects an unpatched binding header
for its before/after comparison. Runtime behavior must also be checked on devices.

## Port behavior

Compact phones use the larger gameplay view and the wider fixed cinematic
profile. D-pad gaps support adjacent directions together. Full-screen logical
bounds round outward to cover fractional-scale edge pixels. Startup loading uses
the bundled game font. The original intro scripts and game assets stay intact;
the 32-bit scripting binding and intro replay bonus are corrected in code.

Credits accept up, up, down, down, left, right, left, right, Action, Jump using
the usual touch positions even while controls are hidden. This saves a per-profile
unlock and adds All Levels to the title menu without marking levels completed.

The renderer remains SDL/OpenGL ES 2, and online add-on downloads are unavailable.
Smoothing stays enabled without a menu toggle. Source generation leaves upstream
src/ untouched. See port/, compat/ and prepare_port.py for the port changes.

## Local archive

Old binaries, caches, transfer archives, private connection settings and the
historical development notes were moved to ../not for github/. They are not
required in a GitHub source upload. Preparation recreates the generated folders.
