# RealtekBluetoothCompat

Lilu companion kext that fixes Bluetooth initialization and BLE pairing for
Realtek USB **`0bda:0852`** (`rtl8852cu` firmware), found on some RTL8852CE cards.

## Compatibility

- **x86_64 macOS 15.8.1, build 24H32 / Darwin 24.6.x.** The build checks the exact
  supported `bluetoothd` binary; other builds are unsupported.
- **Bluetooth USB ID `0bda:0852`.** Check System Information → USB. The RTL8852CE
  Wi-Fi chip name alone does not establish compatibility.
- Existing OpenCore setup with **Lilu 1.7.2**, **BlueToolFixup 2.7.2** and
  **RealtekBluetoothFirmware 1.0.2**. The firmware loader needs the `0bda:0852`
  device match; the installer adds it if missing.

Boot, passkey pairing, typing and reconnection have been tested with an MX Keys S.
Other computers, sleep/wake and audio devices remain untested. Full-SIP
compatibility is unverified; the installer does not change security settings.
This fixes Bluetooth only; it does not add Wi-Fi, AirDrop or AWDL support.

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
- Adds the firmware loader's missing `0bda:0852` personality.
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

Copy `build/RealtekBluetoothCompat.kext` to `OC/Kexts`. Add it after Lilu,
BlueToolFixup and RealtekBluetoothFirmware in `Kernel → Add`:

| Field | Value |
| --- | --- |
| Arch | `x86_64` |
| BundlePath | `RealtekBluetoothCompat.kext` |
| Enabled | `true` |
| ExecutablePath | `Contents/MacOS/RealtekBluetoothCompat` |
| PlistPath | `Contents/Info.plist` |
| MinKernel | `24.6.0` |
| MaxKernel | `24.6.99` |

Ensure the loader has the [required firmware match](docs/FIRMWARE_MATCH.md).
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
