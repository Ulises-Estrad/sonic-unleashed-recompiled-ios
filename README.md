# Sonic Unleashed Recompiled iOS — Day-Stage Arcade

This repository builds a slim, self-contained iOS edition of Sonic
Unleashed Recompiled from the owner's Xbox 360 dump, title update, DLC, and
save data. The final deliverable is one unsigned `.ipa` that Sideloadly can
re-sign and install.

The source is pinned to
[`Markos-Th09/UnleashedRecomp`](https://github.com/Markos-Th09/UnleashedRecomp)
commit `5d5adbc7e6953990be3184e8614787d93940b713` on its `ios` branch.
The working IPA uses this project's exact [tested source snapshot](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/tree/b41f1e64a38244e923d42c0c179cb5bdf09a0b0e); the default branch is not the build provenance.

## Current working build — 1.0.16

[Download the full working IPA](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/download/v1.0.16-working/Sonic-Unleashed-1.0.16-Shader-Warmup-B24.ipa)
· [Release notes and checksum](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/tag/v1.0.16-working)

The owner reported this installed build working and accepted it as the current
baseline on **September 29, 2026**. Development is paused here for now. This is
the exact tested IPA, not a rebuild or a newly repackaged copy. Previous builds
remain available.

- File: `Sonic-Unleashed-1.0.16-Shader-Warmup-B24.ipa`
- Version / numeric build: `1.0.16` / `1.24.1`
- Size: `1,773,524,104` bytes
- SHA-256: `f398aeb5a05984468c7850898965068dfa058ca12f12ce5af3c8ff725c029c11`
- Source: [`b41f1e64a38244e923d42c0c179cb5bdf09a0b0e`](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/tree/b41f1e64a38244e923d42c0c179cb5bdf09a0b0e)
- Native build: [Actions run 24](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/actions/runs/36276171066)

The full package contains the game, update, DLC, bundled save, arcade changes,
touch controls, shader-warmup implementation and Mazuri Act 5 dependency repair.
Its 1,462 bundled data files passed hash and CRC checks; the standard ZIP,
iPhone metadata and executable were verified. GitHub's uploaded asset digest
matches the exact local IPA.

**Not every stage has been tested.** Owner acceptance does not establish
comprehensive device validation or a measured sustained-FPS improvement.
First-use shader compilation can still occur. See the
[1.0.16 implementation notes](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/blob/b41f1e64a38244e923d42c0c179cb5bdf09a0b0e/arcade/shader-warmup.md)
for details; pre-release testing status in those historical notes predates
this acceptance.

Use Sideloadly to install the full IPA over the existing app **without deleting
the app**, preserving its current saves and settings. Do not install a
`compiled-ios-*` release: those are code-only build intermediates.

## Arcade edition

- Keeps the title screen with Continue and Options. Continue opens the day-stage
  selector over the retained globe and stars; story and towns are bypassed.
- L1/R1 changes country and up/down changes act. Options are available from the
  title menu, not the stage selector or in-stage pause menu.
- Includes 48 catalogued daytime stages across Apotos, Mazuri, Spagonia,
  Chun-Nan, Adabat, Holoska, Shamar, Empire City, and Eggmanland.
- Renames the harder DLC variants to `Act N (Hard)` and removes the `[DLC]`
  label.
- Uses the Standard variant of
  [Eggmanland — Day Sections Only](https://gamebanana.com/mods/590834), whose
  QTE transitions skip the Werehog sections.
- Removes medal and media-collectible layers from the retained stages, hides
  the lives and EXP HUD elements, zeroes enemy EXP rewards, and starts Sonic's
  daytime stats at their maximum values.
- Preserves score through deaths; an intentional Restart resets the score.
  Restart is available in stages, not in the stage selector. The lives icon
  and one-up rewards are removed. Max stats do not mean infinite boost.
- Uses the selector's direct stage flow, so Next after the normal rank screen
  returns to stage select without medal or EXP result pages.

The [catalog for this build](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/blob/b41f1e64a38244e923d42c0c179cb5bdf09a0b0e/arcade/stages.json) contains:

| Country | Acts |
| --- | ---: |
| Apotos | 6 |
| Mazuri | 7 |
| Spagonia | 7 |
| Chun-Nan | 7 |
| Adabat | 6 |
| Holoska | 6 |
| Shamar | 4 |
| Empire City | 4 |
| Eggmanland | 1 |

## Touch and DualSense controls

The touch layout has a left virtual stick; L1 and R1 side by side above it;
Square, Triangle, Circle, and Cross in the PlayStation diamond; and R2 above
the diamond's upper-right side. A Start button sits at the bottom center and
maps to the standard Start/Options game input.

The port's existing SDL controller driver already supplies the normal
DualSense layout, including both sticks, D-pad, face buttons, shoulders,
triggers, Options, touchpad/Back, rumble, and player LED. When a connected
controller is identified as a PS5 DualSense, the touch controls disappear and
release any active touches. They reappear automatically on the first rendered
frame after the controller disconnects.

## Why the final IPA is below 2 GB

The earlier 9.2 GB package required ZIP64 and Sideloadly 0.60 rejected it.
Splitting the file for GitHub storage did not change the reconstructed IPA's
ZIP64 structure. The first reduced archive exposed a separate metadata issue:
the upstream template generated `v1.0.3` as an Apple bundle version and did not
declare `iPhoneOS` in `CFBundleSupportedPlatforms`. Both the source patch and
the local injector now normalize those fields before an IPA can pass
verification.

`tools/prepare_arcade_data.py` instead creates a non-destructive reduced data
tree containing the title assets, all 48 selected stages and their required
dependencies, required menu/stage audio, the update, patched executable, save,
and arcade overlay. The 1.0.16 prepared tree is 1,914,326,970 uncompressed
bytes across 1,462 files. All 1,460 accepted 1.0.14 baseline files are unchanged;
only the two missing BossCommon archive files were added. `tools/inject_userdata_into_ipa.py` refuses ZIP64,
validates the app bundle, iPhone platform metadata, and executable, hashes
every injected file, and tests the completed standard ZIP.

## Build and packaging flow

The GitHub Actions workflow compiles the arm64 iPhone executable on a hosted
`macos-15` runner. Xcode supplies the iPhoneOS SDK, Apple linker, Metal tools,
and `codesign`; Sideloadly signs an existing app but cannot replace those
compile-time tools.

The hosted runner builds the code-only intermediate. Full game and save data
are injected and verified locally before an explicitly approved full release
is uploaded. The 1.0.16 working IPA was published unchanged after owner acceptance.

The general local packaging sequence below is historical guidance, not a reason
to rebuild the accepted IPA. Use the pinned source snapshot and 1.0.16 notes
for its exact provenance:

```powershell
python .\tools\build_arcade_mod.py `
  --data-root "C:\path\to\UnleashedRecomp-Windows" `
  --hedge-arc-pack "C:\path\to\HedgeArcPack.exe" `
  --eggmanland-mod "C:\path\to\eggmanland_day_sections_only.zip" `
  --output "C:\path\to\arcade-overlay"

python .\tools\prepare_arcade_data.py `
  --data-root "C:\path\to\UnleashedRecomp-Windows" `
  --save-root "$env:APPDATA\UnleashedRecomp\save" `
  --arcade-overlay "C:\path\to\arcade-overlay" `
  --output "C:\path\to\prepared-arcade-data" `
  --profile sideloadly

python .\tools\inject_userdata_into_ipa.py `
  --compiled-ipa ".\Sonic-Unleashed-Compiled.ipa" `
  --data-root "C:\path\to\prepared-arcade-data" `
  --output ".\Sonic-Unleashed.ipa"
```

## Release visibility

This repository and its releases are public. The owner explicitly requested
publication of the full working IPA, including its bundled game and save data.
The IPA is a release asset, not a file committed to Git. Its original build
provenance metadata is preserved, including local source-folder paths.
