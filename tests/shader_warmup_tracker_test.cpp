#include "shader_warmup_tracker.h"

#include <cassert>
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

int main()
{
    ShaderWarmupTracker tracker;
    assert(tracker.Outstanding() == 0);
    tracker.Wait();
    {
        ShaderWarmupTicket rejectedSubmission(&tracker);
        assert(tracker.Outstanding() == 1);
    }
    assert(tracker.Outstanding() == 0);

    // Parent keeps the gate closed even before discovering the first pipeline.
    ShaderWarmupTicket submittedParent(&tracker);
    submittedParent.Detach();
    {
        auto parent = ShaderWarmupTicket::Adopt(&tracker);
        {
            ShaderWarmupTicket publication(&tracker);
            assert(tracker.Outstanding() == 2);
            publication.Detach(); // Background compilation hands result to render queue.
        }
        assert(tracker.Outstanding() == 2); // Compiler return is NOT completion.
    }
    assert(tracker.Outstanding() == 1); // Parent discovery complete; result still unpublished.
    {
        auto insertOrDrop = ShaderWarmupTicket::Adopt(&tracker);
        assert(tracker.Outstanding() == 1);
    }
    assert(tracker.Outstanding() == 0);

    // Failed enqueue/compile paths release without an acknowledgement consumer.
    try
    {
        ShaderWarmupTicket beforeFailedEnqueue(&tracker);
        throw 1;
    }
    catch (int) {}
    assert(tracker.Outstanding() == 0);
    {
        ShaderWarmupTicket transferred(&tracker);
        auto moved = std::move(transferred);
        assert(!transferred.Active() && moved.Active());
    }
    assert(tracker.Outstanding() == 0);

    // Waiting thread is the loading thread; the simulated render thread stays
    // free to consume each acknowledgement, including duplicates/null results.
    constexpr size_t results = 32;
    ShaderWarmupTicket parent(&tracker);
    for (size_t i = 0; i < results; ++i)
    {
        ShaderWarmupTicket result(&tracker);
        result.Detach();
    }
    parent.Detach();
    std::atomic<bool> waiting{false}, completed{false};
    std::thread loading([&]
    {
        waiting = true;
        tracker.Wait();
        completed = true;
    });
    while (!waiting.load()) std::this_thread::yield();
    for (size_t i = 0; i < results; ++i)
    {
        auto publication = ShaderWarmupTicket::Adopt(&tracker);
        assert(!completed.load());
    }
    assert(tracker.Outstanding() == 1 && !completed.load());
    {
        auto producerFinished = ShaderWarmupTicket::Adopt(&tracker);
    }
    loading.join();
    assert(completed.load() && tracker.Outstanding() == 0);

    // A bounded wait must fail open without pretending that work completed.
    {
        ShaderWarmupTicket delayed(&tracker);
        const auto start = std::chrono::steady_clock::now();
        assert(!tracker.WaitUntil(start + std::chrono::milliseconds(5)));
        assert(tracker.Outstanding() == 1);
        assert(std::chrono::steady_clock::now() - start < std::chrono::seconds(1));
    }
    assert(tracker.WaitUntil(std::chrono::steady_clock::now()));

    // Parent-first completion leaves each insertion/drop acknowledgement owning
    // the gate independently. A null PSO still consumes its acknowledgement.
    {
        ShaderWarmupTicket discovery(&tracker);
        ShaderWarmupTicket validResult(&tracker), duplicateOrNullResult(&tracker);
        validResult.Detach();
        duplicateOrNullResult.Detach();
    }
    assert(tracker.Outstanding() == 2);
    { auto inserted = ShaderWarmupTicket::Adopt(&tracker); }
    assert(tracker.Outstanding() == 1);
    { auto dropped = ShaderWarmupTicket::Adopt(&tracker); }
    assert(tracker.Outstanding() == 0);

    // A DatabaseData worker can release its old task token after enqueue while
    // the independent publication ticket keeps the subsequent loading gate shut.
    std::atomic<bool> databaseTaskCompleted{false}, allowPublication{false};
    std::thread backgroundAndRender([&]
    {
        ShaderWarmupTicket result(&tracker);
        result.Detach();
        databaseTaskCompleted = true;
        while (!allowPublication.load()) std::this_thread::yield();
        auto publication = ShaderWarmupTicket::Adopt(&tracker);
    });
    while (!databaseTaskCompleted.load()) std::this_thread::yield();
    assert(tracker.Outstanding() == 1);
    assert(!tracker.WaitUntil(std::chrono::steady_clock::now()));
    allowPublication = true;
    assert(tracker.WaitUntil(std::chrono::steady_clock::now() + std::chrono::seconds(1)));
    backgroundAndRender.join();

    // Resource disposal is ordered before acknowledgement release for duplicate
    // and failed-insertion paths, mirroring the RAII ordering in ProcAddPipeline.
    struct FakePipeline
    {
        int& alive;
        explicit FakePipeline(int& count) : alive(count) { ++alive; }
        ~FakePipeline() { --alive; }
    };
    int alive = 0;
    ShaderWarmupTicket compiling(&tracker);
    auto compiled = std::make_unique<FakePipeline>(alive);
    FakePipeline* rawQueuedPipeline = compiled.release();
    compiling.Detach();
    {
        auto publication = ShaderWarmupTicket::Adopt(&tracker);
        std::unique_ptr<FakePipeline> incoming(rawQueuedPipeline);
        assert(tracker.Outstanding() == 1 && alive == 1);
        // Duplicate is deliberately not inserted: incoming owns its destruction.
    }
    assert(tracker.Outstanding() == 0 && alive == 0);
}
