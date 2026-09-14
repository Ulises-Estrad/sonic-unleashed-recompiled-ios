# Opt-in performance diagnostics

Separate diagnostic branch based on accepted 1.0.14. Gameplay, assets and rendering settings are unchanged. Create `performance-diagnostics.enabled` in the app Documents directory before launch to enable the recorder. Remove it and relaunch to disable. This opt-in marker will be managed over USB, not through a new game menu.

`IOS-PERF v1` records one summary per second to the existing bounded diagnostic log. It includes presentation rate, samples of existing update/render/fence/presentation/acquisition timers, public NSProcessInfo thermal state (0 nominal, 1 fair, 2 serious, 3 critical), task physical memory footprint, current resolution/FPS limit and active pipeline compilation count. Memory validity is explicit. Timing counters are asynchronous latest samples and may refer to adjacent frames; do not sum them to claim exclusive CPU time or exact per-frame attribution. In particular, skipped timer paths can retain the prior sample. Pair this with Metal HUD per-frame GPU/presentation logging.

No claim of performance improvement. Compilation and device validation are required. Preserve the accepted IPA and saves. Packaging must include the full prepared v12 game data, not distribute the code-only artifact as an installable game.
