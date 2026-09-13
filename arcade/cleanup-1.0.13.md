# Targeted cleanup 1.0.13

Preserves the user-tested 1.0.12 gameplay, stage data, finite boost and menus.

- Hide the complete native `ui_playscreen[/_ev]/add/u_info` medal scene, including its slash and bar children. Native CHudMedalForPause creates this scene at 824A9C88; the extracted Sonic UI contains the medal/number/slash casts, and the existing aspect-ratio table identifies its bar hierarchy. Rings, time, score, energy and pause options stay visible.
- Hide only the world-map `cts_cursor` and `cts_cursor_effect` scene subtrees. Native construction at 8256CD14 creates four directional pieces, followed by the effect at 8256CE14. Preserve country flags, stars, globe, caption and stage-list cursor.
- Explicit Restart clears both checkpoint caches and current EnemyScore/TrickScore immediately before the native score reset at 82304374. The arcade reset wrapper therefore snapshots zero on restart, while ordinary deaths still retain earned score. No persistent flag can leak into subsequent deaths.

Local production-function fixtures passed: death retention, restart clearing, death retention after restart without a checkpoint, repeated restart, absent document, exact UI subtree matches and negative tests for flags/header/highlight/rings/score/boost. Existing 1.0.12 gameplay fixtures also passed.

No prepared game-data changes are needed; reuse the verified v12 gameplay data tree. iPhone acceptance is still required for the visual cleanup and restart/death distinction.
