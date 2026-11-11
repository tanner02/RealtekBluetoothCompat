# RealtekBluetoothCompat

Lilu companion kext that fixes Bluetooth initialization and BLE pairing for
Realtek USB **`0bda:0852`** (`rtl8852cu` firmware, some RTL8852CE cards) and
**`0cb8:c559`** (`rtl8852bu` firmware, RTL8852B).

## Compatibility

- **x86_64 macOS 15.8.1, build 24H32 / Darwin 24.6.x**, or **macOS 26.7.2, build 25G332 / Darwin 25.6.x**. The generator selects the matching layout and checks the exact native `bluetoothd` CodeDirectory and original signed pages. Other binaries are rejected.
- **Bluetooth USB ID `0bda:0852`** on either supported build, or **`0cb8:c559` on
  Tahoe 25G332 only**. Check System Information → USB. The Wi-Fi chip name alone
  does not establish compatibility.
- Existing OpenCore setup with **Lilu 1.7.2**, **BlueToolFixup 2.7.2** and
  **RealtekBluetoothFirmware 1.0.2**. The firmware loader needs the selected USB
  device match; the installer adds it if missing.

Boot, passkey pairing, typing and reconnection have been tested with an MX Keys S.
Other computers, sleep/wake and audio devices remain untested. Full-SIP
compatibility is unverified; the installer does not change security settings.
This fixes Bluetooth only; it does not add Wi-Fi, AirDrop or AWDL support.
The RTL8852B test results and its different patch are documented in
[RTL8852B notes](docs/RTL8852B.md).

## Install

Keep a bootable EFI backup and a wired keyboard available before installing.

1. Install Apple Command Line Tools if needed: `xcode-select --install`.
2. Download and extract this repository, or clone it:
   ```sh
   git clone https://github.com/tanner02/RealtekBluetoothCompat.git
   ```
3. Mount the EFI you boot from, then double-click **`install.command`**.
   You can also run `./install.command` from Terminal in the repository folder.
4. Enter the full path to that EFI's **`OC/config.plist`** when prompted.
   Enter your Mac administrator password when Terminal requests it.
5. When installation succeeds, reboot through the selected EFI.

The installer checks the controller, macOS build and existing dependencies,
fetches pinned build dependencies, runs the build/tests, and then:

- Backs up the selected config, firmware-loader plist and any existing companion
  kext in a timestamped `RealtekBluetoothCompat-backup-*` folder beside the config.
- Copies the built companion into that EFI's `OC/Kexts` folder.
- Adds the firmware loader's missing personality for the detected controller.
- Adds or updates one enabled companion entry after its dependencies in
  `Kernel → Add`, with the supported architecture and kernel limits.
- Checks plist syntax and runs `OC/Tools/ocvalidate` if available. Failed
  installation/validation restores the saved files automatically.

The backup contains recovery instructions. Keep it: interrupted power or a later
boot failure can still require manual recovery. If `ocvalidate` is unavailable,
validate the selected config with the matching OpenCore version before rebooting.
The installer does not download the three prerequisite kexts, mount EFI, change
SIP/NVRAM, restart Bluetooth, or reboot automatically.

This is a **source-only distribution**: Apple executable page fixtures and kexts
containing them are generated locally, rather than included in downloads.

## Manual build and installation

```sh
./scripts/setup-deps.sh
./build.sh
```

The default build retains the `0bda:0852` profile. For `0cb8:c559` on Tahoe:

```sh
./build.sh --device rtl8852b
```

The installer detects the USB ID and builds that profile. Manual builds can
also pass `--binary /path/to/local/bluetoothd`; the exact build guards still apply.

Copy `build/RealtekBluetoothCompat.kext` to `OC/Kexts`. Add it after Lilu,
BlueToolFixup and RealtekBluetoothFirmware in `Kernel → Add`:

| Field | Value |
| --- | --- |
| Arch | `x86_64` |
| BundlePath | `RealtekBluetoothCompat.kext` |
| Enabled | `true` |
| ExecutablePath | `Contents/MacOS/RealtekBluetoothCompat` |
| PlistPath | `Contents/Info.plist` |
| MinKernel | `24.6.0` (Sequoia) or `25.6.0` (Tahoe) |
| MaxKernel | `24.6.99` (Sequoia) or `25.6.99` (Tahoe) |

RTL8852B uses the Tahoe kernel range only. Ensure the loader has the
[required firmware match](docs/FIRMWARE_MATCH.md).
Validate your config before rebooting. Do not bypass the binary guards to force
an unsupported macOS build to work.

## Startup fix in 0.1.2

This version addresses recurring startup crashes in 0.1.1 by moving the injected
code out of the early-read header page and removing USB-enumeration timing from
page patching. Rebuild and reinstall to upgrade. Verified loaded and working after reboot on the test machine.

## Troubleshooting and removal

Check that the kext loaded with `kmutil showloaded | grep RealtekBluetoothCompat`.
See [troubleshooting](docs/TROUBLESHOOTING.md) for diagnostics and the saved
Bluetooth dongle-failure flag.

Boot argument **`-rtkcompatoff`** disables the companion. To uninstall, disable its
`Kernel → Add` entry, remove its kext, and reboot. If boot fails, use your backup
EFI and restore the saved files following `RESTORE.txt` in the installer backup.

## Development and license

[Development notes](docs/DEVELOPMENT.md) cover the guarded patches and local build.
Generated Apple page fixtures and local build output must not be uploaded.

GPL-2.0-only; see [LICENSE](LICENSE) and [third-party notices](docs/THIRD_PARTY_NOTICES.md).
Thanks to [Lilu](https://github.com/acidanthera/Lilu),
[BlueToolFixup / BrcmPatchRAM](https://github.com/acidanthera/BrcmPatchRAM),
[MacKernelSDK](https://github.com/acidanthera/MacKernelSDK),
[RealtekBluetoothFirmware](https://github.com/thegwchr/RealtekBluetoothFirmware)
and [IntelBTPatcher](https://github.com/OpenIntelWireless/IntelBluetoothFirmware).

## Tahoe port (0.2.0)

The Tahoe profile was built from the local 25G332 binary and tested on a Ryzen
5700X3D with the Realtek 0bda:0852 controller. The tester confirmed Bluetooth
working after reboot. Sleep/wake, audio profiles and other Tahoe builds remain
unverified. The Sequoia profile retains its existing addresses and legacy-cache
normalization; it was not hardware-retested during this port.

Native page-guard/ABI/trampoline tests, UBSan and the kmod pointer audit passed.
On the test Hackintosh, ASan aborts in libpthread initialization before main.
Default builds still require ASan; on an affected host explicitly run
`RTKCOMPAT_SKIP_ASAN=1 ./build.sh` (or set this variable for `install.command`).
This prints a warning and does not claim ASan coverage.

See [port details](docs/TAHOE.md). Generated Apple pages and compiled kexts stay local.
