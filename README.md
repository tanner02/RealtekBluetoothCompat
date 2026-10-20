# RealtekBluetoothCompat

Experimental Lilu companion kext for the Bluetooth side of a Realtek RTL8852CE
combo card. Version **0.1.1** has booted successfully and connected a Logitech
MX Keys S on one AMD Hackintosh, **with SIP Debugging Restrictions enabled**.
It replaces an LLDB-based workaround with boot-time, in-memory compatibility
patches. There is no background debugger or runtime helper.

**This is not general RTL8852CE support.** The current match is **USB
`0bda:0852`**, using `rtl8852cu` Bluetooth firmware, on **x86_64 macOS 15.8.1
build 24H32 with one exact `bluetoothd` binary**. Other USB IDs, builds, and
firmware variants are not supported. The Wi-Fi chip name alone is insufficient.

## Tested configuration

| Component | Tested value |
| --- | --- |
| Wi-Fi/Bluetooth combo | RTL8852CE / `rtl8852cu` firmware |
| Bluetooth USB ID | `0bda:0852` |
| macOS | 15.8.1, build **24H32**, Darwin 24.6.0 |
| Architecture | x86_64, AMD Hackintosh |
| Lilu | 1.7.2 |
| BlueToolFixup | 2.7.2 |
| RealtekBluetoothFirmware | 1.0.2 **with the added `0bda:0852` USB personality** |
| Peripheral | Logitech MX Keys S |
| Result | Boot, Bluetooth on, passkey pairing, normal typing and reconnection |

Sleep/wake, audio devices, multiple controllers, and other computers remain
untested. Full-SIP compatibility has **not** been established: debugging
restrictions were enabled, but the test machine's other SIP settings were
customized. This project does not change SIP settings.

## Required firmware-loader device match

The successful test used a **customized RealtekBluetoothFirmware 1.0.2 plist**.
The supplied stock 1.0.2 plist did not match USB `0bda:0852`; the working plist
added exactly one personality, `RealtekBluetoothFirmware_0bda_0852`.

With the stock loader plist and this companion, Bluetooth appeared enabled but
the keyboard would not connect. Restoring the loader's USB match restored
working pairing/connection. **Seeing Bluetooth “On” is not sufficient.** The
companion's USB observer does not make the separate firmware uploader match.

Before installation, check your firmware loader's `IOKitPersonalities`. If it
does not already match `0bda:0852`, follow the [firmware-loader match guide](docs/FIRMWARE_MATCH.md)
and merge the [minimal plist fragment](examples/RealtekBluetoothFirmware-0bda-0852.plist).
The fragment belongs in **RealtekBluetoothFirmware.kext**, not this companion's
`Info.plist`. Do not replace an entire kext plist with the fragment.

## What it fixes

On the tested controller, firmware upload alone left Bluetooth off or unable to
pair BLE devices. The companion applies three corrections:

1. Skip the optional Set Event Mask Page 2 initialization step that the
   controller does not advertise as supported.
2. Issue LE Set Random Address through macOS's own HCI dispatcher before LE
   scan parameter setup, including after a Bluetooth power toggle.
3. Use the baseline 1M PHY readiness path rather than waiting indefinitely for
   an unsolicited PHY event. Faster PHY negotiation is bypassed in that path.

Normal passkey pairing and encryption remain in macOS's normal path. The kext
observes the USB device without opening or resetting it. It does not hook USB
transport methods or modify `/usr/sbin/bluetoothd` on disk.

This does **not** implement firmware loading, Wi-Fi, AWDL, AirDrop, or general
Continuity support. Keep the separate firmware loader and BlueToolFixup.

## Build and install

This is a **source-only release**. Build against your own matching macOS binary:

```sh
git clone https://github.com/tanner02/RealtekBluetoothCompat.git
cd RealtekBluetoothCompat
./scripts/setup-deps.sh
./build.sh
```

Requires x86_64 macOS and Apple Command Line Tools. The scripts fetch pinned
Lilu and MacKernelSDK sources, generate local patch data, run native and
sanitizer tests, and build `build/RealtekBluetoothCompat.kext`. They do not
install anything or change your system configuration.

The generator requires x86_64 CodeDirectory hash
`be939612ec41703dbe1c6f8d004599ebf0e335c0`, and checks each original patch page
and Mach header page against the SHA-256 slots in that exact CodeDirectory.
When the plugin is active, its known cache patches are normalized only in a
temporary build buffer before those signed-page checks. Whole-file read hashes
can vary with cached patches from this plugin or BlueToolFixup, so they are
not used as the support identity. No file is changed.
A macOS version label alone does not establish compatibility. **Do not bypass
the build or runtime guards to force a different binary to work.**

Before testing, keep a bootable backup of your EFI and a wired keyboard. A
kernel extension can prevent booting even when its host tests pass.

1. Confirm your Bluetooth USB ID is `0bda:0852` in System Information → USB.
2. Confirm the firmware loader, Lilu and BlueToolFixup already work in your
   OpenCore configuration. **Verify the firmware loader has the required
   `0bda:0852` match above; stock 1.0.2 did not include it in the supplied plist.**
3. Copy the built kext into your EFI's `OC/Kexts` directory.
4. Add it to `Kernel -> Add` after Lilu and BlueToolFixup. Use `Arch = x86_64`,
   `MinKernel = 24.6.0`, `MaxKernel = 24.6.99`,
   `ExecutablePath = Contents/MacOS/RealtekBluetoothCompat`,
   `PlistPath = Contents/Info.plist`, and `Enabled = true`.
5. Validate your configuration and reboot through that EFI.

Use your own EFI and security configuration. No complete EFI, SMBIOS identity,
NVRAM dump, firmware image, or SIP-setting preset is provided here.

## Verify and recover

```sh
kmutil showloaded | rg RealtekBluetoothCompat
ioreg -r -c RealtekBluetoothCompat -l
ioreg -r -c RealtekBluetoothCompatObserver -l
system_profiler SPBluetoothDataType
csrutil status
```

Expect version 0.1.1, `LiluPluginRegistered = Yes`, the USB observer, and a real
controller address. `CodeValidationRouteReady` is a snapshot at early service
startup, not live telemetry; an early `No` alone does not establish failure.

Boot argument **`-rtkcompatoff`** disables this plugin. To remove it, disable
its `Kernel -> Add` entry (or restore your saved config), then remove the kext
and reboot. If it prevents booting, restore the config from your backup EFI.
See [troubleshooting](docs/TROUBLESHOOTING.md) for the saved dongle-failure flag.

## Source and validation

An early IOResources personality registers with Lilu before its registration
window closes. A separate USB observer enables patches only when the matching
controller is present. The validation hook also requires the exact Apple
CodeDirectory hash, exact file offsets, and exact full-page contents.

The dispatcher payload is position-independent. It occupies verified unused
RX `__TEXT` padding after the last Mach load command and before `__text`,
preserving ASLR. It saves arguments, calls the normal dispatcher for random
address setup, then resumes the original dispatcher prologue.

Native tests exercise page guards, malformed boundaries, idempotence, 800
position-independent dispatches, integer/stack/SIMD arguments, and trampoline
stack restoration. AddressSanitizer and UndefinedBehaviorSanitizer tests pass.
Host tests cannot establish kernel safety. The 0.1.1 boot and keyboard result
above is the hardware validation available so far.

Full Apple executable page fixtures are generated locally under `generated/`
and are intentionally excluded from this repository, together with kext
binaries containing those fixtures. Do not upload that directory or your local
build output. [Development notes](docs/DEVELOPMENT.md) describe the build.

## Credits and license

GPL-2.0-only; see [LICENSE](LICENSE) and [third-party notices](docs/THIRD_PARTY_NOTICES.md).

- [BlueToolFixup / BrcmPatchRAM](https://github.com/acidanthera/BrcmPatchRAM),
  Dhinak G and acidanthera: code-validation routing approach.
- [Lilu](https://github.com/acidanthera/Lilu), vit9696 and contributors:
  plugin API and startup support.
- [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK): build headers/library.
- [RealtekBluetoothFirmware](https://github.com/thegwchr/RealtekBluetoothFirmware):
  separate firmware loader used in testing.
- [IntelBTPatcher](https://github.com/OpenIntelWireless/IntelBluetoothFirmware):
  prior work documenting LE random-address compatibility issues.
