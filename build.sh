#!/bin/sh
# Build only. Does not install a kext, alter NVRAM/SIP, or restart Bluetooth.
set -eu
cd "$(dirname "$0")"
[ "$(uname -m)" = x86_64 ] || { echo 'Only x86_64 macOS is supported.' >&2; exit 1; }
sdk=$(xcrun --sdk macosx --show-sdk-path)
kh='Dependencies/MacKernelSDK'
lilu='Dependencies/Lilu/Lilu'
[ -f "$lilu/Library/plugin_start.cpp" ] && [ -d "$kh/Headers" ] || {
 echo 'Run ./scripts/setup-deps.sh first.' >&2; exit 1;
}
mkdir -p build
xcrun python3 scripts/check-hook.py
xcrun python3 generate.py
xcrun python3 tests/generator.py
xcrun clang++ -arch x86_64 -std=c++14 -Wall -Wextra -Werror tests/host.cpp -o build/host-test
./build/host-test
xcrun clang++ -arch x86_64 -std=c++14 -fsanitize=address,undefined -fno-omit-frame-pointer tests/host.cpp -o build/host-test-sanitized
./build/host-test-sanitized
for src in RealtekBluetoothCompat.cpp "$lilu/Library/plugin_start.cpp"; do
 obj="build/$(basename "$src" .cpp).o"
 xcrun clang++ -arch x86_64 -isysroot "$sdk" -I"$kh/Headers" -I"$kh/PrivateHeaders" -I"$lilu" -mkernel -fapple-kext -fno-builtin -fno-common -fno-exceptions -fno-rtti -std=gnu++14 -DKERNEL -DKERNEL_PRIVATE -DAPPLE -DNeXT -DPRODUCT_NAME=RealtekBluetoothCompat -DMODULE_VERSION=0.1.1 -DLILU_CUSTOM_IOKIT_INIT -Wno-deprecated-declarations -Wno-inconsistent-missing-override -Os -c "$src" -o "$obj"
done
xcrun clang -arch x86_64 -isysroot "$sdk" -I"$kh/Headers" -mkernel -DKERNEL -DKERNEL_PRIVATE -c kmod_info.c -o build/kmod_info.o
xcrun clang++ -arch x86_64 -isysroot "$sdk" -nostdlib -fapple-kext -Wl,-kext -L"$kh/Library/x86_64" build/RealtekBluetoothCompat.o build/plugin_start.o build/kmod_info.o -lkmod -o build/RealtekBluetoothCompat
bundle='build/RealtekBluetoothCompat.kext'
mkdir -p "$bundle/Contents/MacOS"
cp Info.plist "$bundle/Contents/Info.plist"
cp build/RealtekBluetoothCompat "$bundle/Contents/MacOS/RealtekBluetoothCompat"
plutil -lint "$bundle/Contents/Info.plist"
xcrun python3 scripts/verify-kmod.py
echo "Built $bundle. Nothing has been installed."
