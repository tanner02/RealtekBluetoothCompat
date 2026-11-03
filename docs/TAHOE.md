# Tahoe 25G332 port

The build selects one of two layouts using Mach-O load-command size as a hint,
then requires the exact native CodeDirectory hash and original signed-page hashes.
Layout selection alone never authorizes patching. The kernel plugin registers
only for the generated profile's Darwin major version. EFI installer ranges are
24.6.x or 25.6.x, with exact macOS build checks before installation.

| Site | Sequoia 24H32 | Tahoe 25G332 |
| --- | --- | --- |
| Dispatcher entry | 0x146814 | 0x173218 |
| Optional page-2 threshold operand | 0x14493d | 0x17108e |
| Baseline PHY branch | 0x1e4f39 | 0x216551 |
| RX tail-padding payload | 0x9da400 | 0xaa2c00 |

The dispatcher retains the same 18-byte complete-instruction prologue and
SysV varargs ABI. Tahoe call sites still dispatch 0xa5 for the random-address
command and 0xab/0xd7 for scan setup; the hook preserves register, stack and SIMD
arguments while issuing the same random-address command first. The optional
page-2 gate retains the compare against controller version 0x0c. The PHY branch
still bypasses the local/remote 2M readiness path to its zero-result path; its
Tahoe destination and surrounding control flow were inspected in disassembly.
The payload occupies verified zero-filled, file-backed RX __TEXT tail padding,
starting after all sections. It never occupies the Mach header page.

Native tests execute the hook at the actual relative offsets and exercise integer,
stack and SIMD varargs, return values, and stolen-prologue stack restoration.
Generator tests check cache normalization, signed-page tampering and unknown
replacement-site rejection. Installer tests check Tahoe kernel ranges on fixtures.
Hardware result: user confirmed working Bluetooth after reboot. This does not
establish sleep/wake, audio-profile, or cross-build compatibility.

No Apple executable pages, generated manifests, compiled kexts, or EFI data are
included in the source change. Do not distribute generated output.
