#include <cassert>
#include <cstdio>
#include <cstdint>
#include <cstdarg>
#include <cstring>
#include <sys/mman.h>
#include "../PatchEngine.hpp"
#include "../generated/Patches.hpp"
static unsigned scanSetups;
static uint64_t dispatch(unsigned op, void *cb, ...) {
    va_list args; va_start(args, cb);
    if (op == 0xa5) {
        auto address = va_arg(args, unsigned char *);
        assert(!cb && address[0] == 1 && address[5] == 0xc6);
        ++scanSetups; va_end(args); return 0;
    }
    assert(cb == reinterpret_cast<void *>(0x1234));
    for (unsigned i=1; i<=7; ++i) assert(va_arg(args,uint64_t) == 11*i);
    assert(va_arg(args,double)==1.25 && va_arg(args,double)==2.5 && va_arg(args,double)==3.75);
    va_end(args); return 0x123456789abcdef0ULL;
}
int main() {
    unsigned char page[4096], saved[4096];
    for (auto &spec : patchSpecs) {
        memcpy(page,spec.originalPage,4096);
        assert(applyPage(spec,spec.fileOffset,page,4096)==PatchResult::Applied);
        assert(!memcmp(page+spec.pageOffset,spec.replacement,spec.size));
        assert(applyPage(spec,spec.fileOffset,page,4096)==PatchResult::AlreadyApplied);
        memcpy(page,spec.originalPage,4096); page[0]^=1; memcpy(saved,page,4096);
        assert(applyPage(spec,spec.fileOffset,page,4096)==PatchResult::Mismatch);
        assert(!memcmp(page,saved,4096));
        assert(applyPage(spec,spec.fileOffset+4096,page,4096)==PatchResult::NoMatch);
        assert(!memcmp(page,saved,4096));
        assert(applyPage(spec,spec.fileOffset,nullptr,4096)==PatchResult::Mismatch);
        auto invalid=spec; invalid.pageOffset=4090; invalid.size=32;
        assert(applyPage(invalid,invalid.fileOffset,page,4096)==PatchResult::Mismatch);
        invalid.pageOffset=SIZE_MAX;
        assert(applyPage(invalid,invalid.fileOffset,page,4096)==PatchResult::Mismatch);
    }
    auto image=static_cast<unsigned char *>(mmap(nullptr,supportedTextSize,7,MAP_PRIVATE|MAP_ANON,-1,0));
    assert(image!=MAP_FAILED);
    const unsigned char random[]={1,2,3,4,5,0xc6};
    memcpy(replacement0+sizeof(replacement0)-6,random,6);
    memcpy(image+supportedCave,replacement0,sizeof(replacement0));
    memcpy(image+supportedEntry,patchSpecs[2].replacement,patchSpecs[2].size);
    // Direct fake endpoint verifies all hook argument/return preservation at real relative offsets.
    unsigned char absolute[]={0xff,0x25,0,0,0,0,0,0,0,0,0,0,0,0};
    auto target=reinterpret_cast<uint64_t>(&dispatch); memcpy(absolute+6,&target,8);
    memcpy(image+(supportedCave+0xd0),absolute,sizeof(absolute));
    using Fn=uint64_t (*)(unsigned,void *,...);
    auto fn=reinterpret_cast<Fn>(image+supportedEntry);
    const unsigned ops[]={0xab,0xd7,1,0x110};
    for (unsigned j=0;j<100;++j) for(auto op:ops)
        assert(fn(op,reinterpret_cast<void *>(0x1234),11ULL,22ULL,33ULL,44ULL,55ULL,66ULL,77ULL,1.25,2.5,3.75)==0x123456789abcdef0ULL);
    assert(scanSetups==200);
    // Restore actual stolen-prologue trampoline and test return/stack restoration too.
    memcpy(image+supportedCave,replacement0,sizeof(replacement0));
    const unsigned char body[]={0x48,0xb8,0xf0,0xde,0xbc,0x9a,0x78,0x56,0x34,0x12,
        0x48,0x81,0xc4,0x20,0x01,0,0,0x5b,0x41,0x5c,0x41,0x5e,0x41,0x5f,0x5d,0xc3};
    memcpy(image+supportedEntry+18,body,sizeof(body));
    for (unsigned j=0;j<100;++j) for(auto op:ops)
        assert(fn(op,nullptr)==0x123456789abcdef0ULL);
    munmap(image,supportedTextSize);
    puts("PASS: full-page guards, idempotence, malformed boundaries, mismatched build pages; 800 PIC dispatches, 400 scan setups; integer/stack/SIMD varargs, return and real trampoline stack restoration.");
}
