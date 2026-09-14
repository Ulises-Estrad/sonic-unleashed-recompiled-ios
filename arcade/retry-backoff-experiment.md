# Candidate 1: bounded shader-preparation retry experiment

Based on diagnostic build20. All gameplay, quality settings and assets unchanged. The experiment is OFF unless Documents/pipeline-retry-backoff.enabled exists before app launch. Agent manages marker over USB after installation; no game UI changes. First run must be OFF to establish whether this candidate is active.

IOS-RETRY v1 logs cumulative retry passes, stalled passes, actual backoffs and CLOCK_THREAD_CPUTIME_ID CPU milliseconds approximately every five seconds while the worker processes tasks. CPU validity is explicit; thread sleeping with no pending tasks emits nothing, so report gaps are not assumed zero activity. Calculate deltas within a single process. This worker is separate from actual compiler workers. No actual rendering work is removed.

When enabled, sleep_for(1ms) replaces yield only on a fully scanned pass with unresolved tasks AND no completed tasks. A task completion is detected by the original task type changing to Null. Empty queue retains original atomic wait. Unresolved assets are retried, not discarded; no indefinite notification wait is introduced. OS scheduling may oversleep, so loading/readiness regression tests are required.

Local C++ policy test covers all eight boolean combinations. iOS compile and phone performance remain unverified. Keep diagnostic instrumentation identical for A/B; no measured FPS benefit claimed. If worker CPU/retry activity is negligible, deprioritize candidate1. Log activation must be confirmed from IOS-RETRY enabled=false/true after each launch. Follow same route/cooldown at100% resolution and preserve encoder tracking OFF for comparison. Full prepared v12 game data required in final IPA.
