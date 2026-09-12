"""Prepare the owner's data tree for the private day-stage arcade IPA.

The original dump and save are never modified. The default Sideloadly profile
keeps the title and all selected stages while omitting story movies/cutscenes,
unselected packed stages, and optional DLC lighting upgrades. A compatibility
profile retains the full base game and selected-stage lighting additions.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
from typing import Iterable

from build_arcade_mod import DEFAULT_CATALOG, load_catalog, validate_payload


REQUIRED_SAVE_FILES = ("ACH-DATA", "EXT-DATA", "SYS-DATA")
FULL_DIRECTORIES = ("game", "update", "patched")
PREPARED_MANIFEST = "PreparedArcadeData-manifest.json"
SIDELOADLY_MOVIES = {
    "HedgehogEngine_logo.sfd",
    "sega_logo_us.sfd",
    "evmo_title_loop.sfd",
}
SIDELOADLY_SOUND_FILES = {
    # Title, selector/options, clear jingle, and results.
    "bgm_sys_title.csb",
    "bgm_sys_menu.csb",
    "bgm_sys_worldmap.csb",
    "bgm_jingle_stgclear.csb",
    "bgm_jingle_stgclear.cpk",
    "bgm_sys_result.csb",
    "bgm_sys_result.cpk",
    "bgm_sys_result_ng.csb",
    "bgm_sys_result_ng.cpk",
    # Every retained daytime location plus Eggmanland. Mykonos Act 1 has a
    # separate cue sheet in addition to the location-wide one.
    "bgm_stg_myk.csb",
    "bgm_stg_myk_act1.csb",
    "bgm_stg_afr.csb",
    "bgm_stg_euc.csb",
    "bgm_stg_chn.csb",
    "bgm_stg_sea.csb",
    "bgm_stg_snw.csb",
    "bgm_stg_ptr.csb",
    "bgm_stg_nyc.csb",
    "bgm_stg_egb.csb",
}
EGGMANLAND_SUPPORT_ARCHIVES = {
    # ArchiveTree.xml explicitly appends both to Act_EggmanLand. These contain
    # shared player-switch metadata even when the night route is skipped.
    "ActD_EggmanLand",
    "ActN_EggmanLand",
    # The day-only mod skips Werehog sections, but its Stage.stg still names
    # EggmanLand_Evil in SwitchPlayer. Retaining this small dependency chain
    # prevents the stage loader from failing before the skip QTEs can run.
    "EvilSonic",
    "EvilActionCommon",
    "EvilActionCommonGeneral",
    "EvilActionCommon_EggmanLand",
}
# The title-to-selector transition requests this shared family before the
# selector appears. It is not a reachable town, but removing it leaves the
# retail archive loader waiting indefinitely at the post-logo loading screen.
ARCADE_FLOW_SUPPORT_ARCHIVES = {"Town_Common"}
SIDELOADLY_MAX_UNCOMPRESSED_BYTES = 1_900_000_000


def copy_or_link(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode in {"auto", "hardlink"}:
        try:
            os.link(source, destination)
            return "hardlink"
        except OSError:
            if mode == "hardlink":
                raise
    shutil.copy2(source, destination)
    return "copy"


def transfer_files(
    files: Iterable[Path],
    source_root: Path,
    destination_root: Path,
    mode: str,
    counters: dict[str, int],
) -> None:
    for source in sorted(files):
        if not source.is_file():
            continue
        destination = destination_root / source.relative_to(source_root)
        method = copy_or_link(source, destination, mode)
        counters[method] += 1
        counters["files"] += 1
        counters["bytes"] += source.stat().st_size


def catalog_archive_sets(catalog: dict) -> tuple[set[str], dict[str, set[str]]]:
    all_archives: set[str] = set()
    pack_archives: dict[str, set[str]] = {}
    for country in catalog["countries"]:
        for stage in country["stages"]:
            all_archives.add(stage["archive"])
            all_archives.update(stage.get("append", []))
            if geometry := stage.get("geometry"):
                all_archives.add(geometry)
            if stage["source"] != "game":
                pack_archives.setdefault(stage["source"], set()).add(stage["archive"])
    return all_archives, pack_archives


def is_archive_file(filename: str, archives: set[str]) -> bool:
    return any(
        filename.startswith(f"{prefix}{archive}.")
        for archive in archives
        for prefix in ("", "#")
    )


def root_archive_name(filename: str) -> str | None:
    """Return the Hedge archive family for a root .arl/.ar.NN filename."""

    normalized = filename[1:] if filename.startswith("#") else filename
    if normalized.endswith(".arl"):
        return normalized[:-4]
    marker = normalized.rfind(".ar.")
    if marker != -1 and normalized[marker + 4 :].isdigit():
        return normalized[:marker]
    return None


def keep_sideloadly_root_file(path: Path, archives: set[str]) -> bool:
    archive = root_archive_name(path.name)
    if archive is None:
        return True

    if archive in EGGMANLAND_SUPPORT_ARCHIVES:
        return True

    # Keep only the selected daytime members from the large stage family.
    if archive.startswith("ActD_"):
        return archive in archives
    if archive.startswith("ActN_"):
        return False

    if archive in ARCADE_FLOW_SUPPORT_ARCHIVES:
        return True

    # Town, story, Tails, and unused boss archives cannot be reached from the
    # arcade flow. BossEggBeetle is retained because one selected Mazuri act
    # explicitly appends it in the retail stage metadata.
    unreachable_prefixes = (
        "Town_",
        "CmnTown_",
        "Event_",
        "ExStageTails",
        "CmnActN_Terrain_",
    )
    if archive.startswith(unreachable_prefixes):
        return False
    if archive.startswith("Boss"):
        return archive in archives
    if archive in {"StaffRoll", "SuperSonic", "TitleE3"}:
        return False

    if archive.startswith("EvilActionCommon"):
        return archive in EGGMANLAND_SUPPORT_ARCHIVES

    return True


def selected_game_files(data_root: Path, catalog: dict, profile: str) -> list[Path]:
    game_root = data_root / "game"
    if profile == "compatibility":
        return [path for path in game_root.rglob("*") if path.is_file()]

    all_archives, _ = catalog_archive_sets(catalog)
    selected: list[Path] = []
    for path in game_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(game_root)
        parts = relative.parts
        keep = True
        if len(parts) == 1:
            keep = keep_sideloadly_root_file(path, all_archives)
        elif parts[0] == "movie":
            keep = len(parts) == 2 and path.name in SIDELOADLY_MOVIES
        elif parts[0] == "Inspire":
            keep = False
        elif parts[0] == "Sound":
            keep = len(parts) == 2 and (
                path.name in SIDELOADLY_SOUND_FILES
                or path.name.startswith("vs_")
            )
        elif parts[0] == "Packed":
            keep = len(parts) >= 2 and parts[1] in all_archives
        if keep:
            selected.append(path)
    return selected


def selected_dlc_files(data_root: Path, catalog: dict, profile: str) -> list[Path]:
    all_archives, pack_archives = catalog_archive_sets(catalog)
    selected: list[Path] = []
    dlc_root = data_root / "dlc"

    for pack_name, stage_archives in pack_archives.items():
        pack = dlc_root / pack_name
        if not pack.is_dir():
            raise ValueError(f"Missing DLC pack: {pack}")

        for path in pack.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(pack)
            parts = relative.parts
            filename = path.name

            keep = False
            if len(parts) == 1:
                keep = (
                    filename == "DLC.xml"
                    or is_archive_file(filename, {"Application", "WorldMap"})
                    or is_archive_file(filename, stage_archives)
                )
            elif parts[0] == "Languages":
                # Localized DLC application/world-map metadata is small and
                # prevents language-dependent lookups from becoming brittle.
                keep = True
            elif parts[0] == "Packed" and len(parts) >= 2:
                keep = parts[1] in all_archives
            elif parts[0] in {"Additional", "work"} and len(parts) >= 2:
                keep = profile == "compatibility" and parts[1] in all_archives

            if keep:
                selected.append(path)

    return selected


def prepare(
    data_root: Path,
    save_root: Path,
    arcade_overlay: Path,
    output: Path,
    catalog_path: Path,
    mode: str,
    profile: str,
) -> None:
    data_root = data_root.resolve()
    save_root = save_root.resolve()
    arcade_overlay = arcade_overlay.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"Refusing to overwrite output: {output}")
    if not arcade_overlay.is_dir():
        raise ValueError(f"Arcade overlay does not exist: {arcade_overlay}")

    catalog = load_catalog(catalog_path)
    validate_payload(data_root, catalog)
    for filename in REQUIRED_SAVE_FILES:
        if not (save_root / filename).is_file():
            raise ValueError(f"Missing save file: {save_root / filename}")

    output.mkdir(parents=True)
    counters = {"files": 0, "bytes": 0, "hardlink": 0, "copy": 0}
    replaced_families = {
        (p.parent.relative_to(arcade_overlay), p.name.startswith("#"), root_archive_name(p.name))
        for p in arcade_overlay.rglob("*.arl")
        if p.relative_to(arcade_overlay).parts[0] in {"game", "dlc"}
    }

    def not_replaced(path: Path) -> bool:
        relative = path.relative_to(data_root)
        return (relative.parent, path.name.startswith("#"), root_archive_name(path.name)) not in replaced_families

    try:
        for directory in FULL_DIRECTORIES:
            source = data_root / directory
            if not source.is_dir():
                raise ValueError(f"Missing data directory: {source}")
            files = (
                selected_game_files(data_root, catalog, profile)
                if directory == "game"
                else source.rglob("*")
            )
            transfer_files((p for p in files if not_replaced(p)), source, output / directory, mode, counters)

        dlc_files = selected_dlc_files(data_root, catalog, profile)
        transfer_files((p for p in dlc_files if not_replaced(p)), data_root, output, mode, counters)
        transfer_files(
            (save_root / filename for filename in REQUIRED_SAVE_FILES),
            save_root,
            output / "save",
            mode,
            counters,
        )
        transfer_files(arcade_overlay.rglob("*"), arcade_overlay, output, "copy", counters)

        # Re-run payload validation against the reduced tree. This proves every
        # selector entry still has its required archive-list payload.
        validate_payload(output, catalog)
        for pack_name in catalog_archive_sets(catalog)[1]:
            if not (output / "dlc" / pack_name / "DLC.xml").is_file():
                raise ValueError(f"Prepared DLC pack lost its marker: {pack_name}")
        for required in ("cpkredir.ini", "ModsDB.ini", "ArcadeBuild-manifest.json"):
            if not (output / required).is_file():
                raise ValueError(f"Prepared data is missing arcade overlay file: {required}")

        manifest = {
            "schema": 1,
            "stage_count": 48,
            "source_data": str(data_root),
            "source_save": str(save_root),
            "profile": profile,
            "dlc_policy": (
                "selected day stages plus lighting additions"
                if profile == "compatibility"
                else "selected day stages without optional lighting additions"
            ),
            "file_count": counters["files"],
            "uncompressed_bytes": counters["bytes"],
            "hardlinked_files": counters["hardlink"],
            "copied_files": counters["copy"],
        }
        if (
            profile == "sideloadly"
            and counters["bytes"] > SIDELOADLY_MAX_UNCOMPRESSED_BYTES
        ):
            raise ValueError(
                "Sideloadly profile is too large for the standard-ZIP IPA "
                f"budget: {counters['bytes']} > "
                f"{SIDELOADLY_MAX_UNCOMPRESSED_BYTES} bytes"
            )
        (output / PREPARED_MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(output, ignore_errors=True)
        raise

    print(
        f"Prepared {counters['files']} files ({counters['bytes']} bytes) "
        f"for 48-stage arcade IPA: {output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--save-root", required=True, type=Path)
    parser.add_argument("--arcade-overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--mode", choices=("auto", "hardlink", "copy"), default="auto")
    parser.add_argument(
        "--profile",
        choices=("sideloadly", "compatibility"),
        default="sideloadly",
    )
    args = parser.parse_args()
    prepare(
        args.data_root,
        args.save_root,
        args.arcade_overlay,
        args.output,
        args.catalog,
        args.mode,
        args.profile,
    )


if __name__ == "__main__":
    main()
