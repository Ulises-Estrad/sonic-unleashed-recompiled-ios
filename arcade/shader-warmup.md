# Shader warmup candidate 1.0.16

This candidate targets runtime shader-compilation hitches observed in the iOS
Metal HUD. A reported aggregate compilation duration is not evidence of one
continuous frame stall or of a sustained frame-rate bottleneck. Device results
are not established yet.

## Scope

- Track shader warmup through render-cache publication before leaving loading,
  rather than treating background compiler completion as publication.
- Use the existing compiler pool for embedded warmup. The new publication wait
  has a timeout and never blocks the render consumer waiting on itself.
- Retain ordinary synchronous compilation for unknown pipeline combinations;
  do not skip draws, substitute shaders, or change visual quality.
- Reuse compatible Metal 3 binary archives across launches. Cache identity
  includes the exact packaged source revision, schema, GPU, device model and OS
  build. Unsupported, absent, corrupt or unwritable caches fall back to normal
  compilation. This is not a Metal 4 renderer migration.
- Harvest pipeline descriptors and save archives at loading checkpoints, not
  ordinary gameplay frames. Cold/first loads can take longer. Unknown states
  can still compile on their first use during gameplay.
- Record warmup, foreground fallback, archive hits/misses/errors and timings in
  the existing bounded on-device diagnostic reports.

Existing game data, saves, stage rules, controls, resolution and graphics settings
remain unchanged. This candidate also restores two missing `BossCommon` archive
files needed by Mazuri Act 5's shared Egg Beetle assets (see below).
Missing `performance-profile.txt` now selects `baseline`; explicit
profiles from the earlier Performance Lab remain supported. No earlier
experiment has demonstrated a controlled sustained-FPS improvement.

## Verification and device check

The source patch must apply cleanly to the pinned upstream and pass host tests,
then compile on the macOS Actions runner. The public code-only intermediate is
not installable as the self-contained game. Local packaging must inject the
prepared data and verify all accepted 1.0.14 files remain identical. The only
allowed delta is the two restored `BossCommon` files (1462 total), with exact
original-source hashes. ZIP integrity and numeric iOS metadata must also pass.

Install the full IPA over the existing app without deleting it. Verify the
installed version/source and recorded profile first. Keep the same settings and
play the same route twice. Restart/reload the stage once after the first route
so the next loading checkpoint can save any newly encountered pipelines, then
perform a normal relaunch for the repeat route. Compare
`IOS-SHADER-WARMUP`, `IOS-SHADER-FALLBACK`, `IOS-SHADER-SUMMARY` and
`IOS-SHADER-ARCHIVE` records for publication completion, archive save/load/hits,
foreground compile time and errors. Compare matched-temperature frame timing
separately; cache reuse alone is not proof of higher sustained FPS. Do not clear
the user's data or shader cache just to force a cold test.

Preserve the accepted 1.0.14 Arcade and 1.0.15 B23 full IPAs as rollback choices.

## Mazuri Act 5 shared dependency

The device log opened `BossEggBeetle.arl` and `ActD_SubAfrica_04.arl`, then
reported `game:\\BossCommon.arl` missing (`errno=2`) and remained loading. The
slim-data preparation retained the explicitly appended Egg Beetle archive but
removed its common boss-support archive. Restore the original root
`BossCommon.arl` and `BossCommon.ar.00`; keep the existing English-language files
and all stage data unchanged. This restores a dependency, not a playable boss
or new stage. A device retest is still required.
