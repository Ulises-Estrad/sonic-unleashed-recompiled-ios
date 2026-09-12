"""Build the private 48-stage day-only arcade data overlay.

The tool reads the owner's already-extracted Unleashed Recompiled data. It
does not alter that data. Modified XML is emitted through the mod loader's
``work`` directory, so repacking the owner's game archives is unnecessary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPOSITORY_ROOT / "arcade" / "stages.json"
EGGMANLAND_ZIP_SHA256 = "62d763a7813f996e6ae925acf7dc73ad8e82a5a347f08f520d45bd274e5e65d6"
FORBIDDEN_ARCHIVES = {
    "ActD_SubPetra_01",  # scrapped/unused metadata entry
    "ActD_SubPetra_05",  # placeholder without a playable payload
}
REMOVED_LAYER_NAMES = {"medal", "media", "media_evil"}
EXPECTED_COUNTRY_COUNTS = {
    "Apotos": 6,
    "Mazuri": 7,
    "Spagonia": 7,
    "Chun-Nan": 7,
    "Adabat": 6,
    "Holoska": 6,
    "Shamar": 4,
    "Empire City": 4,
    "Eggmanland": 1,
}


def load_catalog(path: Path) -> dict:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    countries = catalog.get("countries")
    if not isinstance(countries, list):
        raise ValueError("Catalog has no countries list")

    if [country.get("name") for country in countries] != list(EXPECTED_COUNTRY_COUNTS):
        raise ValueError("Country order or names differ from the locked arcade catalog")

    archives: set[str] = set()
    stage_count = 0
    for country in countries:
        name = country["name"]
        stages = country.get("stages", [])
        if len(stages) != EXPECTED_COUNTRY_COUNTS[name]:
            raise ValueError(
                f"{name} must contain {EXPECTED_COUNTRY_COUNTS[name]} stages; found {len(stages)}"
            )

        for stage in stages:
            stage_count += 1
            archive = stage.get("archive", "")
            label = stage.get("label", "")
            if not archive or not label:
                raise ValueError(f"Incomplete stage entry in {name}: {stage!r}")
            if archive in FORBIDDEN_ARCHIVES:
                raise ValueError(f"Catalog contains forbidden placeholder stage: {archive}")
            if archive.startswith(("ActN_", "Boss", "Town_", "ExStage", "ActD_Mission")):
                raise ValueError(f"Catalog contains a non-day-action stage: {archive}")
            if "dlc" in label.casefold():
                raise ValueError(f"DLC marker leaked into user-facing label: {label}")
            if archive in archives:
                raise ValueError(f"Duplicate playable archive: {archive}")
            archives.add(archive)

    expected = catalog.get("expected_stage_count")
    if expected != 48 or stage_count != expected:
        raise ValueError(f"Arcade catalog must contain exactly 48 stages; found {stage_count}")
    return catalog


def stage_source_directory(data_root: Path, source: str) -> Path:
    directory = data_root / source if source == "game" else data_root / "dlc" / source
    if not directory.is_dir():
        raise ValueError(f"Missing stage source directory: {directory}")
    return directory


def validate_payload(data_root: Path, catalog: dict) -> None:
    required = (
        data_root / "game" / "default.xex",
        data_root / "game" / "shader.ar",
        data_root / "game" / "#SonicActionCommon.arl",
        data_root / "update" / "default.xexp",
        data_root / "patched" / "default.xex",
    )
    for path in required:
        if not path.is_file():
            raise ValueError(f"Missing required dump file: {path}")

    missing: list[Path] = []
    for country in catalog["countries"]:
        for stage in country["stages"]:
            source = stage_source_directory(data_root, stage["source"])
            archive_list = source / f"#{stage['archive']}.arl"
            if not archive_list.is_file():
                missing.append(archive_list)
            for appended in stage.get("append", []):
                if not (data_root / "game" / f"{appended}.arl").is_file():
                    missing.append(data_root / "game" / f"{appended}.arl")
            geometry = stage.get("geometry")
            if geometry and not any(
                (candidate / f"{geometry}.arl").is_file()
                for candidate in (data_root / "game", source)
            ):
                missing.append(data_root / "game" / f"{geometry}.arl")

    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)
        raise ValueError(f"The selected playable-stage payload is incomplete:\n{formatted}")


def run_extract(tool: Path, archive_list: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(tool), str(archive_list), str(destination), "-E", "-T=ar"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(f"HedgeArcPack failed for {archive_list}:\n{details}")


def remove_collectible_layers(source: Path, destination: Path) -> list[str]:
    # Several retail DLC XML files contain control-byte typos that the game
    # tolerates, but a standards-compliant XML parser correctly rejects. Work
    # on bytes and remove only complete Layer blocks so every unrelated retail
    # byte remains intact.
    data = source.read_bytes()
    removed: list[str] = []

    layer_pattern = re.compile(rb"[ \t]*<Layer>.*?</Layer>[ \t]*\r?\n?", re.IGNORECASE | re.DOTALL)
    name_pattern = re.compile(rb"<Name>\s*([^<]+?)\s*</Name>", re.IGNORECASE)

    def replace_layer(match: re.Match[bytes]) -> bytes:
        name_match = name_pattern.search(match.group(0))
        if not name_match:
            return match.group(0)
        name = name_match.group(1).decode("utf-8", errors="replace").strip()
        if name.casefold() not in REMOVED_LAYER_NAMES:
            return match.group(0)
        removed.append(name)
        return b""

    data = layer_pattern.sub(replace_layer, data)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return removed


def zero_experience_rewards(source: Path, destination: Path) -> int:
    data = source.read_bytes()
    pattern = re.compile(
        rb"(<Experience>)[ \t\r\n]*[0-9]+[ \t\r\n]*(</Experience>)",
        re.IGNORECASE,
    )
    data, replacement_count = pattern.subn(rb"\g<1>0\g<2>", data)
    if replacement_count == 0:
        raise ValueError(f"No enemy experience values found in {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return replacement_count


def sequence_to_selector() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<MicroSequence>
  <SequenceUnit>
    <type>MicroSequence</type>
    <param>
      <FileName>GoToSelectStage</FileName>
    </param>
  </SequenceUnit>
</MicroSequence>
"""


def create_select_xml(catalog: dict, destination: Path) -> None:
    root = ET.Element(
        "StageSelect",
        {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:noNamespaceSchemaLocation": "http://web/chao/project/swa/schema/Select.xsd",
        },
    )

    for country in catalog["countries"]:
        category = ET.SubElement(root, "Category")
        ET.SubElement(category, "Name").text = country["name"]
        common = f"SonicActionCommon_{country['archive_suffix']}"

        for stage in country["stages"]:
            element = ET.SubElement(category, "Stage")
            ET.SubElement(element, "Type").text = "LoadXML"
            # Name is the selector label; Archive remains the real stage ID.
            ET.SubElement(element, "Name").text = stage["label"]
            ET.SubElement(element, "Archive").text = stage["archive"]
            if stage["archive"] != "Act_EggmanLand":
                ET.SubElement(element, "AppendArchive").text = common
            if geometry := stage.get("geometry"):
                ET.SubElement(element, "AppendArchive").text = geometry
            for appended in stage.get("append", []):
                ET.SubElement(element, "AppendArchive").text = appended
            ET.SubElement(element, "IsEvil").text = "false"

    tree = ET.ElementTree(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def locate_eggmanland_xml(source: Path, temporary_root: Path) -> Path:
    root = source
    if source.is_file():
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != EGGMANLAND_ZIP_SHA256:
            raise ValueError(
                "Eggmanland mod ZIP does not match the reviewed GameBanana file "
                f"(expected {EGGMANLAND_ZIP_SHA256}, found {digest})"
            )
        root = temporary_root / "eggmanland-download"
        with zipfile.ZipFile(source) as archive:
            archive.extractall(root)

    direct = root / "Eggmanland"
    if (direct / "Stage.stg.xml").is_file() and (direct / "BaseSonic.set.xml").is_file():
        return direct

    candidates = [
        path
        for path in root.rglob("Eggmanland")
        if (path / "Stage.stg.xml").is_file() and (path / "BaseSonic.set.xml").is_file()
    ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Prefer the explicitly named Standard folder over Extended.
        standard = [path for path in candidates if "extended" not in str(path).casefold()]
        if len(standard) == 1:
            return standard[0]

    packed = [path for path in root.rglob("+#Act_EggmanLand.arl") if "extended" not in str(path).casefold()]
    if len(packed) == 1:
        return packed[0]
    raise ValueError("Could not locate the Standard Eggmanland day-only variant")


def build(
    data_root: Path,
    catalog_path: Path,
    hedge_arc_pack: Path,
    eggmanland_mod: Path,
    output: Path,
) -> None:
    data_root = data_root.resolve()
    hedge_arc_pack = hedge_arc_pack.resolve()
    eggmanland_mod = eggmanland_mod.resolve()
    output = output.resolve()

    if output.exists():
        raise ValueError(f"Refusing to overwrite output: {output}")
    if not hedge_arc_pack.is_file():
        raise ValueError(f"HedgeArcPack was not found: {hedge_arc_pack}")
    if not eggmanland_mod.exists():
        raise ValueError(f"Eggmanland day-only mod was not found: {eggmanland_mod}")

    catalog = load_catalog(catalog_path)
    validate_payload(data_root, catalog)

    with tempfile.TemporaryDirectory(prefix="unleashed-arcade-") as temporary:
        temporary_root = Path(temporary)
        staging = temporary_root / "output"
        mod_root = staging / "mods" / "DayStageArcade"
        work_root = mod_root / "work"

        application = work_root / "Application"
        application.mkdir(parents=True)
        (application / "StartPlay.seq.xml").write_text(sequence_to_selector(), encoding="utf-8")
        (application / "Opening.seq.xml").write_text(sequence_to_selector(), encoding="utf-8")
        create_select_xml(catalog, work_root / "SelectStage" / "Select.xml")

        manifest: dict[str, object] = {
            "schema": 1,
            "stage_count": 48,
            "countries": EXPECTED_COUNTRY_COUNTS,
            "removed_collectible_layers": {},
            "eggmanland_variant": "Standard",
            "flow": "title -> selector -> stage -> rank -> selector",
        }

        sonic_common = temporary_root / "extracted" / "SonicActionCommon"
        run_extract(
            hedge_arc_pack,
            data_root / "game" / "#SonicActionCommon.arl",
            sonic_common,
        )
        enemy_parameters = sonic_common / "EnemySonic.prm.xml"
        if not enemy_parameters.is_file():
            raise ValueError("SonicActionCommon has no EnemySonic.prm.xml")
        manifest["experience_rewards_zeroed"] = zero_experience_rewards(
            enemy_parameters,
            work_root / "SonicActionCommon" / "EnemySonic.prm.xml",
        )

        for country in catalog["countries"]:
            for stage in country["stages"]:
                archive = stage["archive"]
                if stage.get("eggmanland_day_mod"):
                    continue
                source_dir = stage_source_directory(data_root, stage["source"])
                extracted = temporary_root / "extracted" / archive
                run_extract(hedge_arc_pack, source_dir / f"#{archive}.arl", extracted)
                stage_xml = extracted / "Stage.stg.xml"
                if not stage_xml.is_file():
                    raise ValueError(f"{archive} has no Stage.stg.xml in its selected payload")
                removed = remove_collectible_layers(
                    stage_xml,
                    work_root / archive / "Stage.stg.xml",
                )
                manifest["removed_collectible_layers"][archive] = removed

        eggman_source = locate_eggmanland_xml(eggmanland_mod, temporary_root)
        if eggman_source.is_file():
            extracted = temporary_root / "eggmanland-standard"
            run_extract(hedge_arc_pack, eggman_source, extracted)
            eggman_source = extracted
        eggman_destination = work_root / "Act_EggmanLand"
        removed = remove_collectible_layers(
            eggman_source / "Stage.stg.xml",
            eggman_destination / "Stage.stg.xml",
        )
        shutil.copy2(eggman_source / "BaseSonic.set.xml", eggman_destination / "BaseSonic.set.xml")
        manifest["removed_collectible_layers"]["Act_EggmanLand"] = removed

        (mod_root / "mod.ini").write_text(
            """[Desc]
Title="Day Stage Arcade"
Description="48 verified day stages with direct rank-to-selector flow"
Version=1.0
Author="Ulises-Estrad"

[Main]
IncludeDir0="."
IncludeDirCount=1
SaveFile=""
""",
            encoding="utf-8",
        )
        (staging / "cpkredir.ini").write_text(
            """[CPKREDIR]
Enabled=true
ModsDbIni="ModsDB.ini"
""",
            encoding="utf-8",
        )
        (staging / "ModsDB.ini").write_text(
            """[Main]
ActiveModCount=1
ActiveMod0="DayStageArcade"

[Mods]
DayStageArcade="mods/DayStageArcade/mod.ini"

[Codes]
CodeCount=2
Code0="DisableDLCIcon"
Code1="SaveScoreAtCheckpoints"
""",
            encoding="utf-8",
        )
        (staging / "ArcadeBuild-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        shutil.copytree(staging, output)

    print(f"Built 48-stage arcade overlay: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--hedge-arc-pack", required=True, type=Path)
    parser.add_argument("--eggmanland-mod", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(
        args.data_root,
        args.catalog,
        args.hedge_arc_pack,
        args.eggmanland_mod,
        args.output,
    )


if __name__ == "__main__":
    main()
