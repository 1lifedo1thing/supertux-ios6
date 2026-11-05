Installing and compiling SuperTux for iOS
=========================================

This guide covers the iOS 6 port of SuperTux 0.7.0. The app targets ARMv7
devices and has a minimum iOS version of 6.0.

Requirements
------------

You need Python 3.10 or newer to prepare the source, plus internet access to
download dependencies. To compile the app, you need Xcode 6.2 with the
iPhoneOS 8.2 SDK. The app targets iOS 6.

Prepare the source
------------------

On a computer with Python 3.10 or newer, run these commands from the project
root:

```sh
python3 -m pip install -r ios/requirements.txt
python3 ios/fetch_dependencies.py
python3 ios/prepare_port.py
python3 ios/package_data.py
```

These commands prepare `ios/vendor/`, `ios/generated/` and `ios/Resources/`.
Keep `src/`, `data/`, `external/` and `ios/` together.

Compile
-------

Open `ios/SuperTuxIOS.xcodeproj` in Xcode and build the `SuperTuxIOS` target
with the `Release` configuration. Alternatively, run this command from the
project root:

```sh
xcodebuild -project ios/SuperTuxIOS.xcodeproj -target SuperTuxIOS -configuration Release
```

The target runs `ios/build.py` using the system Python 2.7 and Xcode's Apple
compiler. It applies the legacy SDL and 32-bit scripting compatibility
patches.

The build produces:

- `ios/build/SuperTux-0.7.0-iOS6-0.10.ipa`
- `ios/build/org.supertux.ios6_0.10_iphoneos-arm.deb`

The packages are ad hoc signed for installation on jailbroken devices. The DEB
installs the app at `/Applications/SuperTux.app`.

Verify the package
------------------

Verify the IPA with:

```sh
python3 ios/verify_package.py ios/build/SuperTux-0.7.0-iOS6-0.10.ipa
```

This checks the executable architecture, deployment target, bundle identifier,
archive integrity and game data. Runtime behavior should also be tested on
devices.

For further details about the port and its limitations, see
[ios/README.md](ios/README.md).
