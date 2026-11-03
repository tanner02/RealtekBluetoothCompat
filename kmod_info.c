#include <mach/mach_types.h>
extern kern_return_t _start(kmod_info_t *, void *);
extern kern_return_t _stop(kmod_info_t *, void *);
extern kern_return_t RealtekBluetoothCompat_kern_start(kmod_info_t *, void *);
extern kern_return_t RealtekBluetoothCompat_kern_stop(kmod_info_t *, void *);
KMOD_EXPLICIT_DECL(local.RealtekBluetoothCompat,"0.2.0",_start,_stop)
__private_extern__ kmod_start_func_t *_realmain = RealtekBluetoothCompat_kern_start;
__private_extern__ kmod_stop_func_t *_antimain = RealtekBluetoothCompat_kern_stop;
__private_extern__ int _kext_apple_cc = __APPLE_CC__;
