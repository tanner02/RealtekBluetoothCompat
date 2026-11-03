// Build-pinned Lilu companion for Realtek 0bda:0852, x86_64.
// Code-validation routing follows acidanthera BlueToolFixup (GPL-2.0; Dhinak G / acidanthera).
// No USB transport hooks; compatibility instructions run only in bluetoothd.
#include <Headers/kern_api.hpp>
#include <Headers/kern_user.hpp>
#include <Headers/kern_version.hpp>
#include <Headers/plugin_start.hpp>
#include <libkern/c++/OSNumber.h>
#include <sys/random.h>
#include "PatchEngine.hpp"
#include "generated/Patches.hpp"

static mach_vm_address_t originalValidate = 0;
using GetCDHash = int (*)(vnode_t, off_t, unsigned char *, uint8_t *);
static GetCDHash getCDHash = nullptr;
static bool targetActive = false;
static bool routeReady = false;

static uint32_t loggedPages = 0;
static uint32_t refusedPages = 0;
static_assert(PAGE_SIZE == 4096, "This payload is x86_64 4K-page specific");

static void validatePage(vnode_t vnode, memory_object_t pager,
    memory_object_offset_t offset, const void *data, int *validated, int *tainted, int *nx) {
    FunctionCast(validatePage, originalValidate)(vnode, pager, offset, data, validated, tainted, nx);
    // Page validation can precede USB enumeration. Never gate individual code
    // pages on an observer that can change between the payload and dispatcher.
    // Installation enforces the device ID; the path/hash/full-page guards here
    // bind every patch to one supported executable from the first fault onward.
    if (!getCDHash ||
        !data || !validated || !*validated || !tainted || *tainted || !nx || *nx)
        return;
    // Most pages are discarded before vnode/path/hash calls.
    size_t index = 0;
    for (; index < arrsize(patchSpecs); ++index)
        if (patchSpecs[index].fileOffset == offset) break;
    if (index == arrsize(patchSpecs)) return;
    char path[PATH_MAX];
    int length = sizeof(path);
    if (vn_getpath(vnode, path, &length) || strcmp(path, "/usr/sbin/bluetoothd")) return;
    unsigned char cdhash[20]; uint8_t type = 0;
    // Resolve the documented XNU function; never inspect private vnode/cs_blob layouts.
    const uint32_t bit = 1U << index;
    if (getCDHash(vnode, static_cast<off_t>(offset), cdhash, &type) || type != 2 ||
        memcmp(cdhash, supportedCDHash, sizeof(cdhash))) {
        if (!(__atomic_fetch_or(&refusedPages, bit, __ATOMIC_RELAXED) & bit))
            SYSLOG("rtkcompat", "refused unsupported code signature for %s", patchSpecs[index].name);
        return;
    }
    const auto result = applyPage(patchSpecs[index], offset,
        static_cast<unsigned char *>(const_cast<void *>(data)), PAGE_SIZE);
    if (result == PatchResult::Applied && !(__atomic_fetch_or(&loggedPages, bit, __ATOMIC_RELAXED) & bit))
        SYSLOG("rtkcompat", "applied %s at file offset 0x%llx", patchSpecs[index].name, offset);
    if (result == PatchResult::Mismatch &&
        !(__atomic_fetch_or(&refusedPages, bit, __ATOMIC_RELAXED) & bit))
        SYSLOG("rtkcompat", "refused unexpected page %s", patchSpecs[index].name);
}

// The observer never opens, resets, or sends requests to the USB device.
class EXPORT RealtekBluetoothCompat : public IOService {
    OSDeclareDefaultStructors(RealtekBluetoothCompat)
public:
    IOService *probe(IOService *, SInt32 *) override;
    bool start(IOService *) override;
    void stop(IOService *) override;
};
class EXPORT RealtekBluetoothCompatObserver : public IOService {
    OSDeclareDefaultStructors(RealtekBluetoothCompatObserver)
public:
    bool start(IOService *) override;
    void stop(IOService *) override;
};
OSDefineMetaClassAndStructors(RealtekBluetoothCompat, IOService)
OSDefineMetaClassAndStructors(RealtekBluetoothCompatObserver, IOService)
RealtekBluetoothCompat *ADDPR(selfInstance) = nullptr;
IOService *RealtekBluetoothCompat::probe(IOService *provider, SInt32 *score) {
    return IOService::probe(provider, score);
}
bool RealtekBluetoothCompat::start(IOService *provider) {
    if (!IOService::start(provider)) return false;
    ADDPR(selfInstance) = this;
    setProperty("VersionInfo", kextVersion);
    setProperty("LiluPluginRegistered", ADDPR(startSuccess));
    setProperty("CodeValidationRouteReady", __atomic_load_n(&routeReady, __ATOMIC_ACQUIRE));
    registerService();
    SYSLOG("rtkcompat", "early bootstrap service started; Lilu registered=%d", ADDPR(startSuccess));
    return true;
}
void RealtekBluetoothCompat::stop(IOService *provider) {
    ADDPR(selfInstance) = nullptr;
    IOService::stop(provider);
}
bool RealtekBluetoothCompatObserver::start(IOService *provider) {
    if (!IOService::start(provider)) return false;
    auto vendor = OSDynamicCast(OSNumber, provider->getProperty("idVendor"));
    auto product = OSDynamicCast(OSNumber, provider->getProperty("idProduct"));
    if (!vendor || !product || vendor->unsigned32BitValue() != 0x0bda ||
        product->unsigned32BitValue() != 0x0852) return false;
    setProperty("VersionInfo", kextVersion);
    setProperty("SupportedBluetoothdCDHash", supportedCDHashString);
    __atomic_store_n(&targetActive, true, __ATOMIC_RELEASE);
    registerService();
    SYSLOG("rtkcompat", "matched Realtek 0bda:0852; controller observer active");
    return true;
}
void RealtekBluetoothCompatObserver::stop(IOService *provider) {
    __atomic_store_n(&targetActive, false, __ATOMIC_RELEASE);
    IOService::stop(provider);
}

static void patcherReady(void *, KernelPatcher &patcher) {
    getCDHash = reinterpret_cast<GetCDHash>(patcher.solveSymbol(KernelPatcher::KernelID, "_vn_getcdhash"));
    if (!getCDHash || patcher.getError() != KernelPatcher::Error::NoError) {
        patcher.clearError(); getCDHash = nullptr;
        SYSLOG("rtkcompat", "no CDHash accessor; refusing to patch"); return;
    }
    KernelPatcher::RouteRequest route("_cs_validate_page", validatePage, originalValidate);
    if (!patcher.routeMultipleLong(KernelPatcher::KernelID, &route, 1)) {
        patcher.clearError();
        SYSLOG("rtkcompat", "no code-validation route; refusing to patch"); return;
    }
    __atomic_store_n(&routeReady, true, __ATOMIC_RELEASE);
    SYSLOG("rtkcompat", "code-validation route installed; exact-build guard active");
}
static void pluginStart() {
    // Stable within this boot; static-random address, not a resolvable private address.
    read_random(replacement0 + sizeof(replacement0) - 6, 6);
    replacement0[sizeof(replacement0) - 1] |= 0xc0;
    auto error = lilu.onPatcherLoad(patcherReady);
    if (error != LiluAPI::Error::NoError) {
        ADDPR(startSuccess) = false;
        SYSLOG("rtkcompat", "callback registration failed: %d", error);
    }
}
static const char *offArgs[] = {"-rtkcompatoff"};
static const char *debugArgs[] = {"-rtkcompatdbg"};
PluginConfiguration ADDPR(config) {
    xStringify(PRODUCT_NAME), parseModuleVersion(xStringify(MODULE_VERSION)),
    LiluAPI::AllowNormal, offArgs, arrsize(offArgs), debugArgs, arrsize(debugArgs),
    nullptr, 0, static_cast<KernelVersion>(supportedKernel), static_cast<KernelVersion>(supportedKernel), pluginStart
};
