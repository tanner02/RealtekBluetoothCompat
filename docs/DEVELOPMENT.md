# Development

The public source implements the same correction logic as the hardware-tested
0.1.1 local build. Packaging changes only dependency paths and build tooling;
the build itself does not install or change the working system.
The separate `install.command` launcher builds without privileges, then runs
`scripts/install.py` with administrator access to edit the selected EFI only.
Run `python3 tests/installer.py` to exercise installation, idempotence and
rollback on disposable EFI fixtures.

Dependencies are pinned:

- Lilu 1.7.2: `e4748cc081bf060302c7d3c44a643ce1d11b7e1d`
- MacKernelSDK: `3f750085caa17ec3a7880f11c11bf4f48cd6a164`

`generate.py` reads the matching local Apple executable and emits the original
page fixtures, replacement payload and manifest into ignored `generated/`.
Nothing from Apple's full executable pages is checked into Git. Those local
fixtures are used to compare complete pages before any memory write.

`dispatcher-hook-template.s` is the project's assembly source; its 200-byte
assembled template is included for reproducibility. The generator converts
absolute marker operands to relative references at the verified code gap.
`scripts/check-hook.py` reassembles it and verifies the bytes match.

`build.sh` runs the generator, native tests, sanitizer tests, kernel compilation,
plist validation, and kmod startup-pointer audit. No privileged command is used.
It produces a local unsigned Lilu companion kext for an existing compatible
OpenCore setup. It does not alter EFI, SIP, NVRAM, or running services.

Never extend support by changing only a version string, USB ID, or hash. A port
requires inspecting the target binary, preserving ABI and code boundaries,
checking controller semantics, native tests, and a separate hardware boot test.
Do not route USB transport functions merely to make a user-space patch work.

Known limitations: one matching controller is assumed; the CodeValidationRouteReady
property is an early snapshot; boot/runtime behavior on other machines and
sleep/wake are untested. This code is not a replacement firmware uploader.

If the plugin is already active, reads can contain its validated cache patches.
The generator recognizes only its exact four known ranges (including the
per-boot static-random address), reconstructs those ranges in a temporary buffer,
and requires the exact native CodeDirectory hash plus matching SHA-256 slots
for every original patch/header page. Unknown patches in those pages are
rejected. `generate.py --binary /path/to/local/matching/bluetoothd` can be used
for a separate clean local copy. The source file is never written.

## 0.1.2 startup correction

Earlier builds gated independent code-page writes on USB enumeration. An early
header page could be validated while the observer was inactive, followed by a
later patched dispatcher page redirecting into its original zero padding.
Recurrent crashes at 0x2440 are consistent with this failure mode.

The payload now occupies 0x9da400 in signed file-backed RX __TEXT tail padding,
after every section (last section ends at 0x9da370). Generation verifies these
segment/section boundaries, original zero bytes and the original signed page.
Validation no longer gates individual pages on USB enumeration; the installer
checks the device, and the runtime path/hash/full-page guards remain mandatory.
The observer is diagnostic. This avoids split patch decisions as it starts or
stops. The 0.1.2 kext was subsequently verified loaded with Bluetooth working after reboot on the test machine.
