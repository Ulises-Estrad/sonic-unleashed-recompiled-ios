#include "plume_pipeline_cache_policy.h"
#include <cassert>

using namespace plume::pipeline_cache;
static_assert(!SupportsSpecializedArchive(17));
static_assert(SupportsSpecializedArchive(18));
static_assert(SupportsSpecializedArchive(27));
static_assert(!ValidArchiveSize(0));
static_assert(ValidArchiveSize(1));
static_assert(ValidArchiveSize(MaxArchiveBytes));
static_assert(!ValidArchiveSize(MaxArchiveBytes + 1));
static_assert(MaxPendingDescriptors == 1024);
static_assert(ValidNamespace("ba8a62ccc235ae139e63b7900d99b2b816aeb0c1-shader-v1"));
static_assert(!ValidNamespace("unknown-shader-v1"));
static_assert(!ValidNamespace("ba8a62ccc235ae139e63b7900d99b2b816aeb0c1-"));
static_assert(!ValidNamespace("za8a62ccc235ae139e63b7900d99b2b816aeb0c1-shader-v1"));
static_assert(!ValidNamespace("ba8a62ccc235ae139e63b7900d99b2b816aeb0c1-shader/v1"));
static_assert(HarvestBudgetNanoseconds == 5000000000ull);

int main() {
    auto key = CacheKey("shader-v1", "Apple A18 GPU", "iPhone17,4", "24A123");
    assert(key == CacheKey("shader-v1", "Apple A18 GPU", "iPhone17,4", "24A123"));
    assert(key != CacheKey("shader-v2", "Apple A18 GPU", "iPhone17,4", "24A123"));
    assert(key != CacheKey("shader-v1", "Apple A19 GPU", "iPhone17,4", "24A123"));
    assert(key != CacheKey("shader-v1", "Apple A18 GPU", "iPhone17,5", "24A123"));
    assert(key != CacheKey("shader-v1", "Apple A18 GPU", "iPhone17,4", "24A124"));
    assert(CacheKey("a|b", "c", "d", "e") != CacheKey("a", "b|c", "d", "e"));
    assert(key.size() == 16 && key.find_first_not_of("0123456789abcdef") == std::string::npos);
}
