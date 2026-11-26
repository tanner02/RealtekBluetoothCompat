#!/usr/bin/env python3
"""Install only into the selected EFI. No SIP, NVRAM or service changes."""
import argparse
import datetime
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from devices import DEVICES

NAME = 'RealtekBluetoothCompat.kext'
PERSONALITY = 'RealtekBluetoothFirmware_0bda_0852'


def read_plist(path):
    with path.open('rb') as handle:
        return plistlib.load(handle)


def check_device_kernel(device):
    if int(platform.release().split('.')[0]) not in DEVICES[device]['kernels']:
        kernels = ', '.join(str(k) for k in DEVICES[device]['kernels'])
        raise ValueError(device + ' requires Darwin ' + kernels + ' and a matching supported macOS build.')


def atomic_write(path, data):
    stat = path.stat()
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, stat.st_mode & 0o777)
        if os.geteuid() == 0:
            os.chown(temporary, stat.st_uid, stat.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def encode_plist(value, original):
    fmt = plistlib.FMT_BINARY if original.startswith(b'bplist') else plistlib.FMT_XML
    return plistlib.dumps(value, fmt=fmt, sort_keys=False)


def plan(config, device='rtl8852ce'):
    """Validate and calculate edits without writing anything."""
    controller = DEVICES[device]
    vendor, product = controller['vendor'], controller['product']
    check_device_kernel(device)
    personality = f'RealtekBluetoothFirmware_{vendor:04x}_{product:04x}'
    config = config.expanduser().resolve(strict=True)
    if config.name != 'config.plist':
        raise ValueError('Select an OpenCore file named config.plist.')
    kexts = config.parent / 'Kexts'
    original = config.read_bytes()
    value = plistlib.loads(original)
    entries = value['Kernel']['Add']
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ValueError('Kernel -> Add must be an array of dictionaries.')
    required = {}
    for name in ('Lilu.kext', 'BlueToolFixup.kext', 'RealtekBluetoothFirmware.kext'):
        matches = [(i, e) for i, e in enumerate(entries) if e.get('BundlePath') == name]
        if len(matches) != 1 or matches[0][1].get('Enabled') is not True:
            raise ValueError('Exactly one enabled Kernel -> Add entry is required for ' + name)
        i, entry = matches[0]
        if entry.get('Arch', 'Any') not in ('Any', 'x86_64'):
            raise ValueError(name + ' must support x86_64.')
        for key, default in (('MinKernel', '0.0.0'), ('MaxKernel', '999.999.999')):
            version = tuple(int(p) for p in (entry.get(key) or default).split('.'))
            current = tuple(int(p) for p in platform.release().split('.'))
            if (key == 'MinKernel' and current < version) or (key == 'MaxKernel' and current > version):
                raise ValueError(name + ' is excluded by ' + key)
        bundle = kexts / name
        if not bundle.is_dir() or bundle.is_symlink():
            raise ValueError('Missing or symlinked dependency: ' + str(bundle))
        info = read_plist(bundle / 'Contents/Info.plist')
        executable = bundle / 'Contents/MacOS' / info['CFBundleExecutable']
        if not executable.is_file():
            raise ValueError('Missing dependency executable: ' + str(executable))
        required[name] = i
    if required['Lilu.kext'] > required['BlueToolFixup.kext']:
        raise ValueError('Lilu must precede BlueToolFixup in Kernel -> Add.')
    firmware = kexts / 'RealtekBluetoothFirmware.kext/Contents/Info.plist'
    if firmware.is_symlink():
        raise ValueError('Refusing a symlinked firmware Info.plist.')
    fw_original = firmware.read_bytes()
    fw = plistlib.loads(fw_original)
    if fw.get('CFBundleIdentifier') != 'org.thegwchr.RealtekBluetoothFirmware':
        raise ValueError('Unexpected firmware-loader bundle identifier.')
    personalities = fw['IOKitPersonalities']
    has_match = any(p.get('idVendor') == vendor and p.get('idProduct') == product
                    and p.get('IOClass') == 'RealtekBluetoothFirmware'
                    and p.get('IOProviderClass') == 'IOUSBHostDevice'
                    for p in personalities.values() if isinstance(p, dict))
    if not has_match:
        if personality in personalities:
            raise ValueError('Conflicting existing firmware personality; inspect it manually.')
        fragment = read_plist(ROOT / f'examples/RealtekBluetoothFirmware-{vendor:04x}-{product:04x}.plist')
        personalities[personality] = fragment['IOKitPersonalities'][personality]
    # Replace duplicate/stale companion entries and put one after all prerequisites.
    entries[:] = [e for e in entries if e.get('BundlePath') != NAME]
    position = max(i for i, e in enumerate(entries) if e.get('BundlePath') in required) + 1
    entries.insert(position, {
        'Arch': 'x86_64', 'BundlePath': NAME, 'Comment': 'Realtek Bluetooth compatibility',
        'Enabled': True, 'ExecutablePath': 'Contents/MacOS/RealtekBluetoothCompat',
        'MaxKernel': platform.release().split('.')[0]+'.6.99', 'MinKernel': platform.release().split('.')[0]+'.6.0', 'PlistPath': 'Contents/Info.plist',
    })
    target = kexts / NAME
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError('Refusing unexpected companion target: ' + str(target))
    return config, firmware, target, encode_plist(value, original), encode_plist(fw, fw_original)


def check_machine(device='auto'):
    if platform.system() != 'Darwin' or platform.machine() != 'x86_64':
        raise ValueError('Requires x86_64 macOS.')
    build = subprocess.check_output(['/usr/bin/sw_vers', '-buildVersion'], text=True).strip()
    if (build, '.'.join(platform.release().split('.')[:2])) not in {('24H32','24.6'),('25G332','25.6')}:
        raise ValueError('Supported builds: 24H32 / Darwin 24.6.x or 25G332 / Darwin 25.6.x only.')
    usb = plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg', '-a', '-r', '-c', 'IOUSBHostDevice']))

    def matches(node, vendor, product):
        if isinstance(node, dict):
            return (node.get('idVendor') == vendor and node.get('idProduct') == product
                    or any(matches(v, vendor, product) for v in node.values()))
        return isinstance(node, list) and any(matches(v, vendor, product) for v in node)

    candidates = DEVICES if device == 'auto' else (device,)
    for name in candidates:
        controller = DEVICES[name]
        if matches(usb, controller['vendor'], controller['product']):
            check_device_kernel(name)
            return name
    ids = ', '.join(f"{DEVICES[name]['vendor']:04x}:{DEVICES[name]['product']:04x}" for name in candidates)
    raise ValueError('Required USB Bluetooth controller was not found: ' + ids + '.')


def install(config, device='rtl8852ce'):
    config, firmware, target, new_config, new_fw = plan(config, device)
    source = ROOT / 'build' / NAME
    info = read_plist(source / 'Contents/Info.plist')
    if info.get('CFBundleIdentifier') != 'local.RealtekBluetoothCompat':
        raise ValueError('Unexpected built kext identifier.')
    if not (source / 'Contents/MacOS/RealtekBluetoothCompat').is_file():
        raise ValueError('Build the kext first.')
    observer = info['IOKitPersonalities']['RealtekBluetoothCompatObserver']
    controller = DEVICES[device]
    if (observer.get('idVendor'), observer.get('idProduct')) != (controller['vendor'], controller['product']):
        raise ValueError('Built kext does not match the controller; rebuild with --device ' + device + '.')
    # Back up before any EFI edits. A separate directory is created on every run.
    backup = Path(tempfile.mkdtemp(
        prefix='RealtekBluetoothCompat-backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-'),
        dir=str(config.parent)))
    shutil.copy2(config, backup / 'config.plist')
    shutil.copy2(firmware, backup / 'firmware-Info.plist')
    had_kext = target.exists()
    if had_kext:
        shutil.copytree(target, backup / NAME, symlinks=True)
    (backup / 'RESTORE.txt').write_text(
        'Boot another EFI if needed. Restore config.plist to:\n' + str(config) +
        '\nRestore firmware-Info.plist to:\n' + str(firmware) +
        ('\nReplace the installed companion with the saved ' + NAME if had_kext else
         '\nRemove the newly installed ' + str(target)) + '\n')
    print('Backup: ' + str(backup), flush=True)
    stage = Path(tempfile.mkdtemp(prefix='.rtkcompat-stage-', dir=str(target.parent)))
    changed = False
    try:
        shutil.copytree(source, stage / NAME)
        changed = True
        if had_kext:
            shutil.rmtree(target)
        os.replace(stage / NAME, target)
        atomic_write(firmware, new_fw)
        # Write config last, so it never points at a partially copied kext.
        atomic_write(config, new_config)
        subprocess.run(['/usr/bin/plutil', '-lint', str(config), str(firmware)], check=True)
        validator = config.parent / 'Tools/ocvalidate'
        if validator.is_file() and os.access(validator, os.X_OK):
            subprocess.run([str(validator), str(config)], check=True)
        else:
            print('ocvalidate is not present in OC/Tools; full OpenCore schema validation was skipped.')
    except BaseException:
        if changed:
            atomic_write(config, (backup / 'config.plist').read_bytes())
            atomic_write(firmware, (backup / 'firmware-Info.plist').read_bytes())
            if target.exists():
                shutil.rmtree(target)
            if had_kext:
                shutil.copytree(backup / NAME, target, symlinks=True)
            print('Installation failed; original files restored. Backup: ' + str(backup))
        raise
    finally:
        shutil.rmtree(stage)
    print('Installed. Reboot through the EFI you selected when ready. No reboot was triggered.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='read-only preflight')
    parser.add_argument('--device', choices=('auto', *DEVICES), default='auto', help='controller profile (default: auto-detect)')
    parser.add_argument('--print-device', action='store_true', help='read-only preflight and print the selected device')
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        device = check_machine(args.device)
        if args.check or args.print_device:
            plan(args.config, device)
            print(device if args.print_device else 'Controller, macOS build and EFI prerequisites passed (' + device + ').')
        else:
            install(args.config, device)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Installer error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
