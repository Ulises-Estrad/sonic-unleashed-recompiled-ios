# Gameplay refinement 1.0.12

Implemented for the next device test; not yet verified on iPhone.

- Keep the existing globe/flags/stars. Lock only manual globe-camera rotation on both Continue and stage-return routes; leave list navigation and L1/R1 intact.
- Stage pause: Resume, Restart, Options, Quit Game. World-map pause does not gain Restart.
- Remove the whole lives HUD scene, including the remaining Sonic icon. Keep time, score, rings and finite boost gauges.
- Remove ItemBox and ItemBoxEvil extra-life objects from copies of all 48 catalogued stage archives. A separate native patch suppresses the 100-ring reward and jingle.
- Next on the normal rank screen sends the same completion request used after the original EXP menu. Do not instantiate the medal/EXP menus or pause for them.
- Set the actual daytime progression getters to Speed 11 and Ring Energy 6. Do not change the live boost amount, drain, refill, or capacity beyond the native max-level behavior.
- Remove remaining pause medal numerator/denominator nodes, whose names differ from the world-map counters.

## Evidence and checks

Owned executable, pinned iOS source and extracted SkillParameter.xml were used for the native traces:

- 8251A1C8 / 8251A228: daytime level getters, reading progression fields +85F0 / +85F8. Sonic's initialization at 82321830 uses both. The old guessed on-disk SYS-DATA edits were removed.
- 824AF6E8 / 824B05E0: stage pause rows and actions; restart action 8, transition 2.
- 824A891C..824A89A0: native EXP exit sends MsgChangeStageMode(10). Rank Next at 824A0C8C now sends that request directly and bypasses the obsolete medal-menu pause at 824A0D48.
- 8230C9E8: isolated 100-ring extra-life routine.
- ItemBox / ItemBoxEvil factories 827A15B8 / 827A15F0 select CObjGetItem types 0 / 1; their collection branches award item type 4 and play objes_extend.
- 82486258: world-map camera input; temporary +E8 flag skips only analog rotation, not camera interpolation or rendering.
- CHudMedalForPause at 824A9C00 uses num_nume_m, num_deno_m, num_nume_s, num_deno_s in ui_playscreen.

Local extracted-production-hook fixtures test exact stat writes, unchanged surrounding memory, completion message routing/refcount cleanup/fallback, 100-ring suppression, and pause counts/actions in normal and mission-style stages. Native-selector tests include the independent camera path. Country-caption tests still pass.

The data-refinement tool refuses existing outputs, preserves source data, edits only the two verified life-object types, and round-trips every changed archive against all expected members. Current pass: 216 objects removed across 48 checked stage archives. These counts include objects in inactive layers; they are not a claim that 216 pickups were reachable in day gameplay.

Device acceptance still required: restart several stage types; collect 100 rings without a 1-Up; confirm finite boost at max upgrade capacity; finish a stage and return from rank directly to the selector; verify HUD and globe consistency.
