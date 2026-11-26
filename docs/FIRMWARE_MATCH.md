# Required RealtekBluetoothFirmware match for USB 0bda:0852

The working hardware test requires **two separate kexts to match the controller**:

- `RealtekBluetoothFirmware.kext` uploads the Realtek firmware.
- `RealtekBluetoothCompat.kext` applies the macOS compatibility patches.

This companion already includes its USB observer match. It cannot substitute
for a missing personality in the firmware loader.

## Exact stock-versus-working difference

Both compared firmware-loader plists identify
`org.thegwchr.RealtekBluetoothFirmware`, version **1.0.2**. The supplied stock
plist has 83 personalities; the working plist has 84. The only semantic change
is this added entry inside the existing `IOKitPersonalities` dictionary:

```xml
<key>RealtekBluetoothFirmware_0bda_0852</key>
<dict>
    <key>CFBundleIdentifier</key>
    <string>org.thegwchr.RealtekBluetoothFirmware</string>
    <key>IOClass</key>
    <string>RealtekBluetoothFirmware</string>
    <key>IOMatchCategory</key>
    <string>RealtekBluetoothFirmware</string>
    <key>IOProbeScore</key>
    <integer>4000</integer>
    <key>IOProviderClass</key>
    <string>IOUSBHostDevice</string>
    <key>idVendor</key>
    <integer>3034</integer>
    <key>idProduct</key>
    <integer>2130</integer>
</dict>
```

`3034` is decimal for `0x0BDA`; `2130` is decimal for `0x0852`.
These are USB IDs for the tested Bluetooth function, not the Wi-Fi PCI ID.
No other firmware-loader fields changed. Merging the repository's fragment
into the supplied stock plist was checked to reproduce the working plist
exactly as a parsed property list.

## Merge into your loader

1. Check your own Bluetooth USB VID/PID. This addition is only for `0bda:0852`;
   do not substitute an unrelated controller's IDs to force a match.
2. Back up the **firmware loader's** `Contents/Info.plist` in your boot EFI:
   `EFI/OC/Kexts/RealtekBluetoothFirmware.kext/Contents/Info.plist`.
3. Check whether any existing personality already matches these IDs. If one
   does, do not add a duplicate; newer/different upstream builds may include it.
4. If the match is absent, merge the entry above into that plist's existing
   `IOKitPersonalities` dictionary, preserving the rest of the loader plist.
   The [example fragment](../examples/RealtekBluetoothFirmware-0bda-0852.plist)
   contains only that dictionary addition. **It is not a complete Info.plist.**
5. Keep the firmware loader's existing enabled OpenCore entry. This plist edit
   does not require a second loader entry or another kext. Validate the plist
   and reboot through the EFI you edited.

Do **not** put this entry in
`RealtekBluetoothCompat.kext/Contents/Info.plist`. The bundle identifier and
class in the fragment intentionally name the separate firmware loader.

## What was observed

The same machine was tested with the companion fix and the supplied stock
firmware-loader plist: Bluetooth appeared enabled, but MX Keys S could not
connect. Switching back to the customized firmware-loader plist restored
working connections. Other builds/controllers remain untested.

Check that the loader actually matches the USB device and completes firmware
upload. `FirmwareLoaded = Yes` belongs to the USB provider in the tested loader;
the loader service also exposes `fw_name = rtl8852cu`. A Bluetooth On indicator
or the companion's observer alone does not establish successful firmware upload.

This repository supplies the match data and instructions, not a modified
firmware-loader binary or a complete EFI. Updating/replacing the firmware loader
can overwrite a local plist addition, so recheck its match after an update.

## USB 0cb8:c559 (RTL8852B)

Use [RealtekBluetoothFirmware-0cb8-c559.plist](../examples/RealtekBluetoothFirmware-0cb8-c559.plist)
for this controller instead of the `0bda:0852` fragment. It is also a dictionary
addition to the existing firmware-loader plist. The installer adds the selected
match without replacing other personalities. Build the companion with
`./build.sh --device rtl8852b`; this profile supports Tahoe 25G332 only.
See [RTL8852B notes](RTL8852B.md) for the patch and hardware results.
