# Sonic Unleashed Recompiled iOS — Day-Stage Arcade

This private repository builds a slim, self-contained iOS edition of Sonic
Unleashed Recompiled from the owner's Xbox 360 dump, title update, DLC, and
save data. The final deliverable is one unsigned `.ipa` that Sideloadly can
re-sign and install.

The source is pinned to
[`Markos-Th09/UnleashedRecomp`](https://github.com/Markos-Th09/UnleashedRecomp)
commit `5d5adbc7e6953990be3184e8614787d93940b713` on its `ios` branch.

## Download

Private release:
[`day-stage-arcade-v1`](https://github.com/Ulises-Estrad/sonic-unleashed-recompiled-ios/releases/tag/day-stage-arcade-v1)

- File: `Unleashed-Day-Stage-Arcade.ipa`
- Size: `1,752,629,894` bytes (1.632 GiB)
- SHA-256: `c469ab761632f53a972a59ab1e99d944734a04d691caede3afa588f10dc9e88d`

Download that one IPA and drag it directly into Sideloadly. There are no
numbered parts and no reconstruction step.

## Arcade edition

- Keeps the Sonic Unleashed title screen. Pressing Start continues directly
  to the stage selector; story, towns, and the world map are bypassed.
- Uses a country-first selector: left/right changes country and up/down changes
  act. Start/Options opens the Recompiled options menu.
- Includes 48 verified daytime stages across Apotos, Mazuri, Spagonia,
  Chun-Nan, Adabat, Holoska, Shamar, Empire City, and Eggmanland.
- Renames the harder DLC variants to `Act N (Hard)` and removes the `[DLC]`
  label.
- Uses the Standard variant of
  [Eggmanland — Day Sections Only](https://gamebanana.com/mods/590834), whose
  QTE transitions skip the Werehog sections.
- Removes medal and media-collectible layers from the retained stages, hides
  the lives and EXP HUD elements, zeroes enemy EXP rewards, and starts Sonic's
  daytime stats at their maximum values.
- Keeps lives at 99 and preserves the complete score through deaths.
- Uses the selector's direct stage flow, so Next after the normal rank screen
  returns to stage select without medal or EXP result pages.

The authoritative catalog is [`arcade/stages.json`](arcade/stages.json):

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
the diamond's upper-right side.

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
and arcade overlay. The current prepared tree is 1,746,641,792 uncompressed
bytes across 1,377 files. `tools/inject_userdata_into_ipa.py` refuses ZIP64,
validates the app bundle, iPhone platform metadata, and executable, hashes
every injected file, and tests the completed standard ZIP.

## Build and packaging flow

The GitHub Actions workflow compiles the arm64 iPhone executable on a hosted
`macos-15` runner. Xcode supplies the iPhoneOS SDK, Apple linker, Metal tools,
and `codesign`; Sideloadly signs an existing app but cannot replace those
compile-time tools.

The hosted runner downloads only the three private recompiler inputs from the
private `private-build-inputs-v1` release. Full game and save data stay on the
owner's PC until the local injection step.

The reproducible local sequence is:

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
  --compiled-ipa ".\Unleashed-Day-Stage-Arcade-Compiled.ipa" `
  --data-root "C:\path\to\prepared-arcade-data" `
  --output ".\Unleashed-Day-Stage-Arcade.ipa"
```

## Private data policy

Game files, save data, and completed IPAs are not committed to Git. The private
build inputs and final self-contained IPA are release assets in this private
repository. Keep the repository and releases private.
