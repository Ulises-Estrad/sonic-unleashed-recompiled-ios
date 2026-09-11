# Sonic Unleashed Recompiled iOS - private build

This private repository produces a self-contained, unsigned iOS IPA with:

- The playable `ios` port of Unleashed Recompiled.
- DualSense-style multitouch controls.
- The owner's game, title update, DLC, patched executable, and save data.

The source is pinned to commit
`5d5adbc7e6953990be3184e8614787d93940b713` from
`Markos-Th09/UnleashedRecomp:ios`. The local patch adds the touch overlay,
read-only bundled-game-data support, first-launch save seeding, and
Sideloadly-friendly packaging.

## Download and reconstruct the IPA

GitHub requires each release asset to be smaller than 2 GiB. The final IPA is
therefore stored as numbered parts with a SHA-256 manifest.

1. Download every `Unleashed-DualSense-Touch.ipa.partNNN` file from the latest
   release.
2. Download `Unleashed-DualSense-Touch.ipa.manifest.json` and `join-ipa.ps1`
   into the same directory.
3. Run this in PowerShell:

   ```powershell
   .\join-ipa.ps1
   ```

4. Drag the reconstructed `Unleashed-DualSense-Touch.ipa` into Sideloadly.

The join script verifies each part and the complete IPA before reporting
success.

## Why GitHub uses a Mac runner

The `Compile unsigned iOS IPA` workflow runs on GitHub's hosted `macos-15`
runner. Compiling an arm64 iPhone executable requires Apple's iPhoneOS SDK,
linker, Metal tools, and `codesign`, which are supplied with Xcode. No personally
owned Mac is needed. Sideloadly performs the final device signing; it does not
compile C++ source into an iOS Mach-O executable.

The workflow downloads only three private build inputs (`default.xex`,
`default.xexp`, and `shader.ar`), clones the pinned iOS source, applies the touch
patch, and publishes a small compiled IPA.

The full 9.2 GiB game-data tree never passes through the hosted Mac. A local
packaging step on the owner's PC injects `game`, `update`, `dlc`, `patched`, and
`save` into the compiled app, verifies every bundled file, and creates the final
self-contained IPA. That IPA is split into sub-2-GB assets only for GitHub
storage and becomes one file again before Sideloadly.

## Private data policy

No game or save data is committed to Git. The three build inputs and final IPA
parts are stored only in private releases. Keep this repository private.
