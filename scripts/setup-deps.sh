#!/bin/sh
# Download pinned build dependencies; never modifies EFI or system configuration.
set -eu
cd "$(dirname "$0")/.."
mkdir -p Dependencies
fetch() {
 name=$1; url=$2; commit=$3
 target="Dependencies/$name"
 if [ ! -d "$target" ]; then
  git clone --no-checkout "$url" "$target"
  git -C "$target" fetch origin "$commit"
  git -C "$target" checkout --detach "$commit"
 fi
 [ "$(git -C "$target" remote get-url origin)" = "$url" ] || {
  echo "Unexpected origin in $target" >&2; exit 1;
 }
 actual=$(git -C "$target" rev-parse HEAD 2>/dev/null || true)
 if [ "$actual" != "$commit" ]; then
  [ -z "$(git -C "$target" status --porcelain)" ] || {
   echo "Refusing to replace local changes in $target" >&2; exit 1;
  }
  git -C "$target" fetch origin "$commit"
  git -C "$target" checkout --detach "$commit"
 fi
 [ "$(git -C "$target" rev-parse HEAD)" = "$commit" ]
}
fetch Lilu https://github.com/acidanthera/Lilu.git e4748cc081bf060302c7d3c44a643ce1d11b7e1d
fetch MacKernelSDK https://github.com/acidanthera/MacKernelSDK.git 3f750085caa17ec3a7880f11c11bf4f48cd6a164
