# Title-only Options and world-map input 1.0.14

- In-stage pause: Resume, Restart, Quit Game.
- World-map pause: Resume, Quit Game. Options remains available from the title menu.
- Remove the separate stage-list Start-to-Options shortcut, not just the native pause row. Native Start handling remains available.
- Strip Square/X from every world-map frame's SWA pad and from all five native cached button masks, including transition states outside normal stage-list input isolation. Restore original input after the frame so stage gameplay is unaffected.
- Preserve 1.0.13's medal panel and globe crosshair cleanup, restart score reset, ordinary death score retention, and all prepared game data.
- Initialize the original `CWorldMapSun` effect's native daytime pose after construction. Its `word_map_sun.part-bin`, material and texture remain in TitleModel; this does not restore time-change input or medal icons. Normal globe positioning calls 82573958 at 82583678; the direct-entry route needs an initial pose without waiting for that navigation branch. Visual confirmation on iPhone remains pending.

Local native selector and gameplay fixtures pass: Options no longer opens from stage-select Start; native pause counts and actions agree; X is blocked in normal and transitional world-map cached input and restored outside it; list navigation, country switching and gameplay hooks remain intact. Phone verification is still required for 1.0.14.

The reported Apotos Act 2 exit was traced to an iOS per-process memory-limit kill, not a normal exception. The user's saved 8192 shadows and 4x MSAA were identified; the user confirmed the stage loads after switching to 1024 shadows and no MSAA. Do not undo the working 1.0.13 cleanup or alter saved graphics settings/data for this build. Device logs stay local.
