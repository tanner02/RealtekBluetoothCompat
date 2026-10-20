# Changelog

## Installer and documentation

- Add a double-click installer that prompts for the OpenCore config path, builds
  locally, backs up affected files, merges the firmware match and config entry,
  and restores originals if installation or validation fails.
- Simplify the README around compatibility, installation and recovery.
- No companion code or version changes.

## Documentation update — firmware-loader match

- Correct the tested prerequisite: RealtekBluetoothFirmware 1.0.2 used a custom
  `0bda:0852` personality absent from the supplied stock plist.
- Include a minimal merge fragment and explain why Bluetooth On alone does not
  establish firmware-loader compatibility. No companion code/version changes.

## 0.1.1

- Register with Lilu through an early IOResources bootstrap.
- Detect USB `0bda:0852` with a separate observer.
- Apply build-pinned optional-command, LE random-address and baseline-PHY fixes.
- Add exact CodeDirectory/full-page guards and refusal logs.
- Verified boot and MX Keys S typing with SIP Debugging Restrictions enabled.
- Publish source-only packaging with pinned dependencies and local-only fixtures.

## 0.1.0 (not released)

Booted, but the USB-only startup path did not activate Bluetooth.
