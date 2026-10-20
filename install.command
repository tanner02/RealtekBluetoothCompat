#!/bin/sh
# Double-click in Finder, or run ./install.command from Terminal.
set -eu
cd "$(dirname "$0")"
trap 'echo; echo "Installer stopped. Press Return to close."; read -r unused' EXIT
echo 'RealtekBluetoothCompat installer'
echo 'Mount your EFI first. Keep a bootable EFI backup and a wired keyboard.'
echo 'Requires existing Lilu, BlueToolFixup and RealtekBluetoothFirmware kexts.'
printf 'Enter the full path to your OpenCore config.plist: '
IFS= read -r config
# Accept paths pasted with one surrounding pair of quotes; never evaluate input.
case "$config" in
  \"*\") config=${config#\"}; config=${config%\"} ;;
esac
[ -n "$config" ] || { echo 'No config.plist path supplied.'; exit 1; }
xcode-select -p >/dev/null 2>&1 || {
 echo 'Install Apple Command Line Tools with xcode-select --install, then run again.'; exit 1;
}
python=$(xcrun --find python3)
config=$("$python" -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve(strict=True))' "$config")
"$python" scripts/install.py --check "$config"
./scripts/setup-deps.sh
./build.sh
echo 'Build passed. Administrator access is used only for the EFI installation.'
sudo -- "$python" scripts/install.py "$config"
