#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
struct PatchSpec {
    uint64_t fileOffset;
    size_t pageOffset;
    size_t size;
    const unsigned char *originalPage;
    const unsigned char *replacement;
    const char *name;
};
enum class PatchResult { NoMatch, Mismatch, Applied, AlreadyApplied };
// No allocations, pointer chasing, filesystem I/O or kernel-private structures.
static inline PatchResult applyPage(const PatchSpec &spec, uint64_t fileOffset,
                                   unsigned char *data, size_t pageSize) {
    if (fileOffset != spec.fileOffset) return PatchResult::NoMatch;
    if (!data || pageSize != 4096 || !spec.size || spec.pageOffset > pageSize ||
        spec.size > pageSize - spec.pageOffset) return PatchResult::Mismatch;
    const size_t end = spec.pageOffset + spec.size;
    if (memcmp(data, spec.originalPage, spec.pageOffset) ||
        memcmp(data + end, spec.originalPage + end, pageSize - end))
        return PatchResult::Mismatch;
    if (!memcmp(data + spec.pageOffset, spec.replacement, spec.size))
        return PatchResult::AlreadyApplied;
    if (memcmp(data + spec.pageOffset, spec.originalPage + spec.pageOffset, spec.size))
        return PatchResult::Mismatch;
    memcpy(data + spec.pageOffset, spec.replacement, spec.size);
    return PatchResult::Applied;
}
