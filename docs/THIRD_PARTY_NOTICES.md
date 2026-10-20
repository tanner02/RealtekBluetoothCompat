# Third-party notices

The code-validation routing approach is adapted from `BlueToolFixup.cpp`,
created by Dhinak G (2021) in acidanthera/BrcmPatchRAM. The local source used
commit `65389020769837e92e9fb939bac34bd9a3e25bb2`. That project's GPL version 2
license is provided as the repository LICENSE.

Lilu plugin startup code and headers are fetched at the pinned commit in
`scripts/setup-deps.sh`. Lilu is copyright (c) 2016–2018 vit9696 and contributors,
under BSD-3-Clause; its license is reproduced in Lilu-LICENSE.txt. Preserve that
notice with any distribution incorporating its code.

MacKernelSDK is fetched separately at its pinned commit. Its files retain their
respective Apple and upstream notices; they are not bundled in this repository.

The XNU `vn_getcdhash(vnode_t, off_t, unsigned char *, uint8_t *)` signature was
checked against Apple's xnu-11417.140.69 source:
https://github.com/apple-oss-distributions/xnu/blob/xnu-11417.140.69/bsd/vfs/vfs_subr.c

Apple's executable is not included. Full original-page fixtures and compiled
kexts containing them are generated locally and excluded from publication.
No Apple code in those local generated files is relicensed by this project's
GPL notice. The hashes, patch offsets, small compatibility sequences, and the
project's own assembly implement this build-specific compatibility mechanism.
