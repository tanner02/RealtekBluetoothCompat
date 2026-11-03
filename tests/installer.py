#!/usr/bin/env python3
"""Exercise EFI changes on disposable fixtures, never the mounted EFI."""
import importlib.util
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.oc = self.root / 'EFI with spaces/OC'
        self.oc.mkdir(parents=True)
        self.config = self.oc / 'config.plist'
        self.firmware = self.oc / 'Kexts/RealtekBluetoothFirmware.kext/Contents/Info.plist'
        self.target = self.oc / 'Kexts' / installer.NAME
        self.value = {'PrivateUnrelated': {'Data': b'unchanged', 'Flag': True}, 'Kernel': {'Add': []}}
        for name in ('Lilu', 'BlueToolFixup', 'RealtekBluetoothFirmware'):
            contents = self.oc / 'Kexts' / (name + '.kext') / 'Contents'
            (contents / 'MacOS').mkdir(parents=True)
            (contents / 'MacOS' / name).write_bytes(b'fixture')
            info = {'CFBundleExecutable': name}
            if name == 'RealtekBluetoothFirmware':
                info.update(CFBundleIdentifier='org.thegwchr.RealtekBluetoothFirmware', IOKitPersonalities={'Other': {'idVendor': 1}})
            (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
            self.value['Kernel']['Add'].append({'BundlePath': name + '.kext', 'Enabled': True, 'Arch': 'Any', 'MinKernel': '', 'MaxKernel': ''})
        self.config.write_bytes(plistlib.dumps(self.value, fmt=plistlib.FMT_BINARY))
        source = self.root / 'build' / installer.NAME / 'Contents'
        (source / 'MacOS').mkdir(parents=True)
        (source / 'MacOS/RealtekBluetoothCompat').write_bytes(b'new-kext')
        (source / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'local.RealtekBluetoothCompat'}))
        (self.root / 'examples').mkdir()
        fragment = installer.ROOT / 'examples/RealtekBluetoothFirmware-0bda-0852.plist'
        (self.root / 'examples' / fragment.name).write_bytes(fragment.read_bytes())
        self.addCleanup(patch.stopall)
        patch.object(installer, 'ROOT', self.root).start()
        patch.object(installer.platform, 'release', return_value='24.6.0').start()

    def test_success_repeat_and_preservation(self):
        installer.install(self.config)
        installer.install(self.config)
        value = installer.read_plist(self.config)
        self.assertEqual(value['PrivateUnrelated'], self.value['PrivateUnrelated'])
        self.assertTrue(self.config.read_bytes().startswith(b'bplist'))
        entries = value['Kernel']['Add']
        self.assertEqual([e['BundlePath'] for e in entries], ['Lilu.kext', 'BlueToolFixup.kext', 'RealtekBluetoothFirmware.kext', installer.NAME])
        fw = installer.read_plist(self.firmware)['IOKitPersonalities']
        self.assertEqual(fw[installer.PERSONALITY]['idProduct'], 2130)
        self.assertEqual(fw['Other'], {'idVendor': 1})
        self.assertEqual(len(list(self.oc.glob('RealtekBluetoothCompat-backup-*'))), 2)

    def test_tahoe_kernel_range(self):
        with patch.object(installer.platform, 'release', return_value='25.6.0'):
            installer.install(self.config)
        entries = installer.read_plist(self.config)['Kernel']['Add']
        entry = next(e for e in entries if e['BundlePath'] == installer.NAME)
        self.assertEqual(entry['MinKernel'], '25.6.0')
        self.assertEqual(entry['MaxKernel'], '25.6.99')

    def test_validation_failure_rolls_back_existing_kext(self):
        self.target.mkdir()
        (self.target / 'old').write_bytes(b'old-kext')
        before = self.config.read_bytes(), self.firmware.read_bytes()
        with patch.object(installer.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'plutil')):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.install(self.config)
        self.assertEqual(before, (self.config.read_bytes(), self.firmware.read_bytes()))
        self.assertEqual(list(self.target.iterdir()), [self.target / 'old'])
        self.assertEqual((self.target / 'old').read_bytes(), b'old-kext')

    def test_ocvalidate_failure_rolls_back(self):
        tools = self.oc / 'Tools'
        tools.mkdir()
        validator = tools / 'ocvalidate'
        validator.write_text('#!/bin/sh\nexit 1\n')
        validator.chmod(0o755)
        before = self.config.read_bytes(), self.firmware.read_bytes()
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(self.config)
        self.assertEqual(before, (self.config.read_bytes(), self.firmware.read_bytes()))
        self.assertFalse(self.target.exists())

    def test_failure_removes_new_kext(self):
        before = self.config.read_bytes(), self.firmware.read_bytes()
        with patch.object(installer.subprocess, 'run', side_effect=OSError('validation unavailable')):
            with self.assertRaises(OSError):
                installer.install(self.config)
        self.assertFalse(self.target.exists())
        self.assertEqual(before, (self.config.read_bytes(), self.firmware.read_bytes()))

    def test_disabled_dependency_refused_before_backup(self):
        self.value['Kernel']['Add'][0]['Enabled'] = False
        self.config.write_bytes(plistlib.dumps(self.value))
        with self.assertRaises(ValueError):
            installer.install(self.config)
        self.assertFalse(list(self.oc.glob('RealtekBluetoothCompat-backup-*')))

    def test_existing_match_is_preserved_and_companion_deduplicated(self):
        fw = installer.read_plist(self.firmware)
        fw['IOKitPersonalities']['Existing'] = {'idVendor': 3034, 'idProduct': 2130, 'IOClass': 'RealtekBluetoothFirmware', 'IOProviderClass': 'IOUSBHostDevice', 'Custom': 'preserve'}
        self.firmware.write_bytes(plistlib.dumps(fw))
        self.value['Kernel']['Add'].insert(0, {'BundlePath': installer.NAME, 'Enabled': False})
        self.value['Kernel']['Add'].append({'BundlePath': installer.NAME, 'Enabled': True})
        self.config.write_bytes(plistlib.dumps(self.value))
        plan = installer.plan(self.config)
        self.assertEqual(plistlib.loads(plan[4]), fw)
        entries = plistlib.loads(plan[3])['Kernel']['Add']
        self.assertEqual(sum(e['BundlePath'] == installer.NAME for e in entries), 1)
        self.assertEqual(entries[-1]['BundlePath'], installer.NAME)


if __name__ == '__main__':
    unittest.main()
