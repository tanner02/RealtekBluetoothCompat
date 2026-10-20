# Troubleshooting

## Unsupported binary

The supported binary is macOS 15.8.1 build 24H32's exact x86_64 `bluetoothd`,
identified by the hashes in the README. Updates can change the binary even when
the visible macOS version looks similar. The generator and kext intentionally
refuse unknown versions. Removing a check is not a port to another build.

## Kext loaded but observer missing

Version 0.1.0 used only USB matching and did not activate Bluetooth. Version
0.1.1 uses an early IOResources bootstrap plus a separate USB observer. Check
both classes in IORegistry, the loaded version, Lilu order and USB ID. A loaded
kext alone does not prove registration, matching, or patches were applied.

## Bluetooth still cannot turn on

A previous initialization failure can leave the following NVRAM flag set:

```sh
nvram bluetoothExternalDongleFailed
```

If it is `%01`, clear that specific flag using your existing authorized NVRAM
setup and reboot through the corrected EFI:

```sh
sudo nvram bluetoothExternalDongleFailed=%00
```

This is not a SIP change. If the write is denied, do not disable additional
protections just to force it; use your existing OpenCore recovery process.
The flag was cleared during the successful hardware test.

## Bluetooth is On but the keyboard cannot connect

First verify the **firmware-loader match**, not just this companion's observer.
The tested stock RealtekBluetoothFirmware 1.0.2 plist lacked USB `0bda:0852`.
With that stock plist, Bluetooth could appear enabled but MX Keys S connections
failed. Adding the loader personality restored working connections.

See [the exact match and merge instructions](FIRMWARE_MATCH.md). A loader service
for the device and a successful firmware upload are required. Do not add the
firmware-loader personality to RealtekBluetoothCompat's own plist.

## Connected keyboard does not immediately reconnect

The tested MX Keys S sometimes needed a keypress to wake after a Bluetooth
power toggle. Select the Mac's Easy-Switch channel and press a key. Do not
assume an idle keyboard will reconnect within a fixed short timeout.

## Reporting an issue

Include macOS build, Bluetooth USB VID/PID, loaded kext versions, whether the
two IORegistry classes exist, and the exact symptom. Redact serial numbers,
Bluetooth/MAC addresses and personal device names. Do not post an entire EFI,
SMBIOS configuration, NVRAM dump, or unrelated system logs.
