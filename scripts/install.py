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
import tempfile

ROOT = Path(__file__).resolve().parent.parent
NAME = 'RealtekBluetoothCompat.kext'
PERSONALITY = 'RealtekBluetoothFirmware_0bda_0852'


def read_plist(path):
    with path.open('rb') as handle:
        return plistlib.load(handle)


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


def plan(config):
    """Validate and calculate edits without writing anything."""
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
    has_match = any(p.get('idVendor') == 3034 and p.get('idProduct') == 2130
                    and p.get('IOClass') == 'RealtekBluetoothFirmware'
                    and p.get('IOProviderClass') == 'IOUSBHostDevice'
                    for p in personalities.values() if isinstance(p, dict))
    if not has_match:
        if PERSONALITY in personalities:
            raise ValueError('Conflicting existing firmware personality; inspect it manually.')
        fragment = read_plist(ROOT / 'examples/RealtekBluetoothFirmware-0bda-0852.plist')
        personalities[PERSONALITY] = fragment['IOKitPersonalities'][PERSONALITY]
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


def check_machine():
    if platform.system() != 'Darwin' or platform.machine() != 'x86_64':
        raise ValueError('Requires x86_64 macOS.')
    build = subprocess.check_output(['/usr/bin/sw_vers', '-buildVersion'], text=True).strip()
    if (build, '.'.join(platform.release().split('.')[:2])) not in {('24H32','24.6'),('25G332','25.6')}:
        raise ValueError('Supported builds: 24H32 / Darwin 24.6.x or 25G332 / Darwin 25.6.x only.')
    usb = plistlib.loads(subprocess.check_output(['/usr/sbin/ioreg', '-a', '-r', '-c', 'IOUSBHostDevice']))

    def matches(node):
        if isinstance(node, dict):
            return (node.get('idVendor') == 3034 and node.get('idProduct') == 2130
                    or any(matches(v) for v in node.values()))
        return isinstance(node, list) and any(matches(v) for v in node)

    if not matches(usb):
        raise ValueError('Required USB Bluetooth controller 0bda:0852 was not found.')


def install(config):
    config, firmware, target, new_config, new_fw = plan(config)
    source = ROOT / 'build' / NAME
    info = read_plist(source / 'Contents/Info.plist')
    if info.get('CFBundleIdentifier') != 'local.RealtekBluetoothCompat':
        raise ValueError('Unexpected built kext identifier.')
    if not (source / 'Contents/MacOS/RealtekBluetoothCompat').is_file():
        raise ValueError('Build the kext first.')
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
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        check_machine()
        if args.check:
            plan(args.config)
            print('Controller, macOS build and EFI prerequisites passed.')
        else:
            install(args.config)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Installer error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
