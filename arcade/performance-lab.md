# Performance Lab 1.0.15 (experimental)

This is not a replacement for the accepted, tentative-complete 1.0.14 Arcade
build. No FPS gain has yet been demonstrated on device. The full local IPA must
retain the identical 1,460-file game-data manifest. Never install a code-only
Actions intermediate or publish the owner's full data.

## One IPA, independent launch profiles

`Documents/performance-profile.txt` selects the profile on the next launch.
It is read once; do not change ownership/pacing policies during a running scene.
Missing file defaults to `all`; invalid/unreadable content fails to `baseline`.
The old `pipeline-retry-backoff.enabled` marker is ignored by this build.

| Profile | Retry backoff | Cached clear state | Finer limiter sleep |
| --- | --- | --- | --- |
| baseline | off | off | off |
| retry | on | off | off |
| clear-cache | off | on | off |
| limiter | off | off | on |
| all | on | on | on |
| all-no-retry | off | on | on |
| all-no-clear-cache | on | off | on |
| all-no-limiter | on | on | off |

The native 60-FPS target, simulation, assets, resolution, AA, shadows, GI,
motion blur, saves and touch/controller behavior are unchanged.

1. Retry: 1-ms sleep only after an unresolved shader-preparation pass makes no
   progress; active work still proceeds immediately.
2. Clear-state cache: device-owned reuse of the exact original no-depth-write
   descriptor. The comparison baseline also repairs the original retained-state
   leak, releasing temporary objects after GPU completion because command buffers
   use unretained references. Thus it is a leak-corrected baseline, not an exact
   old-binary comparison. If cache allocation fails, use the uncached path.
3. Limiter: same deadline/interval, but sleep toward a 0.5-ms guard rather than
   the original 2-ms guard plus whole-ms rounding. Oversleep/pacing regression
   is possible and must be checked. This likely matters more in lighter scenes
   than in Adabat when frames already exceed the target interval.

Submission ordering, attachment load/store behavior, draw calls, shader quality
and residency scheduling are deliberately unchanged. Their counters identify
whether a separately justified experiment is worth attempting next.

## Reports and retrieval

The home-screen name is **Unleashed Perf Lab**, version **1.0.15**. Local packaging
sets a distinct numeric build number and `PerformanceLabSourceSHA`. Every launch
unconditionally logs the actual profile, switches, build, settings samples and
whether persistence succeeded. Verify this record before asking for a test.

`Documents/PerformanceLab/session-<timestamp>.log` contains bounded (8-MiB),
app-owned records, flushed at each five-second sample or phase change. Existing
unified/app logging remains available; capture does not depend on visible Metal
HUD options. No save/config deletion or network reporting occurs. Logs remain
until explicitly removed, so long-term users should manage accumulated reports.

Records include frame counts/times, 0.5-ms histogram percentile upper bounds,
slow-frame counts, process and present-thread CPU clocks, latest asynchronous GPU
timestamps, thermal state, memory, exact graphics settings, loading/pause/stage
epochs, shader retry snapshots and cumulative Metal counters. CPU time can exceed
wall time for a multithreaded process. GPU duration is not GPU utilization. Native
profiler values are asynchronous, not additive exclusive costs. Creation timing
samples one in 64 state allocations; it is wall time, not driver-only CPU time.

The read-only `tools/performance_lab.py collect` fetches reports. `profile --name`
is an explicit, scoped write of only the profile file; close the app first.
`analyze` rejects loading, paused, menu, mixed-stage and malformed windows, groups
matching settings/stage/thermal readings, and reports cumulative-counter deltas
within a process. Window percentiles are not pooled-run percentiles. End-of-window
thermal/settings snapshots are not proof conditions were constant throughout.

## Comparison protocol

Keep 100% resolution and accepted options fixed. First verify the new build and
report headers, then compare the same Adabat Act 1 route/duration at similar
starting thermal state, charging, brightness and controller conditions. Compare
`baseline` versus `all`, then `all` versus each `all-no-*` profile. Use individual
profiles when interactions or a regression make attribution ambiguous. Repeat
controls; do not attribute route, shader-cache warmup or thermal drift to a toggle.
One all-on run cannot establish which change helped or hurt.

Check lighter Apotos gameplay for limiter behavior, plus pause/restart/death,
results/menus, background/resume, loading and rendering correctness. Compare
immediate throughput and sustained heat separately. All 48 levels still require
eventual testing. Preserve the accepted IPA and all comparison logs. Promote
only repeatable improvements that exceed variation without regressions.
