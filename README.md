# Sonic Unleashed Recompiled iOS — Day-Stage Arcade

This repository builds a slim, self-contained iOS edition of Sonic
Unleashed Recompiled from the owner's Xbox 360 dump, title update, DLC, and
save data. The final deliverable is one unsigned `.ipa` that Sideloadly can
re-sign and install.

The source is pinned to
[`Markos-Th09/UnleashedRecomp`](https://github.com/Markos-Th09/UnleashedRecomp)
commit `5d5adbc7e6953990be3184e8614787d93940b713` on its `ios` branch.

## Latest release — 1.0.18

[Download the full IPA](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/download/v1.0.18/Sonic-Unleashed-1.0.18.ipa)
· [Release notes and checksum](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/tag/v1.0.18)

This controller-only release removes enemy XP from the remaining stage-specific
reward tables, hides Chip's 3D model, and disables Files sharing for the app's
Documents folder. Install with Sideloadly over your existing copy using the
same signing settings to retain saves and settings.

The IPA passed package and bundled-data verification. The changed gameplay
and Files behavior are awaiting an iPhone playtest. The
[device-tested 1.0.16 build](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/tag/v1.0.16-working)
and [1.0.17 release](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/tag/v1.0.17)
are still available. Pick a full release IPA for Sideloadly.

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

The [stage catalog](arcade/stages.json) contains these acts.

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

## Controller controls

Play with a connected controller such as a DualSense. The iOS build uses the
port's SDL controller mappings for sticks, D-pad, buttons, triggers, Options,
touchpad/Back, rumble, and player LED.

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

The local packaging sequence builds and bakes the arcade overlay before
preparing the bundled data and injecting it into the IPA.

```powershell
python .\tools\build_arcade_mod.py `
  --data-root "C:\path\to\UnleashedRecomp-Windows" `
  --hedge-arc-pack "C:\path\to\HedgeArcPack.exe" `
  --eggmanland-mod "C:\path\to\eggmanland_day_sections_only.zip" `
  --output "C:\path\to\arcade-overlay"

python .\tools\bake_arcade_archives.py `
  --data-root "C:\path\to\UnleashedRecomp-Windows" `
  --overlay "C:\path\to\arcade-overlay" `
  --hedge-arc-pack "C:\path\to\HedgeArcPack.exe" `
  --output "C:\path\to\arcade-baked"

python .\tools\prepare_arcade_data.py `
  --data-root "C:\path\to\UnleashedRecomp-Windows" `
  --save-root "$env:APPDATA\UnleashedRecomp\save" `
  --arcade-overlay "C:\path\to\arcade-baked" `
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
