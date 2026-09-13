"""Remove verified extra-life object types from an existing bundled arcade tree.

ItemBox -> factory 827A15B8 -> CObjGetItem type 0; ItemBoxEvil ->
827A15F0 -> type 1. Both collectible branches send item type 4 and play
objes_extend (82692CE0 / 82692D9C). Do not remove rings or energy pickups.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

from build_arcade_mod import load_catalog, run_extract

LIFE_OBJECT = re.compile(rb"[ \t]*<(ItemBox|ItemBoxEvil)>.*?</\1>[ \t]*(?:\r?\n)?", re.DOTALL)


def remove_life_objects(data: bytes) -> tuple[bytes, list[dict]]:
    removed = []
    def replace(match):
        identifier = re.search(rb"<SetObjectID>(\d+)</SetObjectID>", match.group())
        if not identifier:
            raise ValueError("Extra-life object has no SetObjectID")
        removed.append({"type": match.group(1).decode(), "id": int(identifier.group(1))})
        return b""
    return LIFE_OBJECT.sub(replace, data), removed


def refine(source: Path, output: Path, catalog_path: Path, tool: Path):
    source, output, tool = source.resolve(), output.resolve(), tool.resolve()
    if output.exists() or output == source or source in output.parents:
        raise ValueError("Output must be a new, separate directory")
    catalog = load_catalog(catalog_path)
    archives = {stage["archive"] for country in catalog["countries"] for stage in country["stages"]}
    sources = [source / "game", *(source / "dlc").iterdir()]
    print("Copying known-working bundled data; original files remain unchanged", flush=True)
    shutil.copytree(source, output)
    records = []
    found = set()
    with tempfile.TemporaryDirectory(prefix="arcade-life-items-") as temporary:
        scratch = Path(temporary)
        for directory in sources:
            for name in sorted(archives):
                archive = directory / f"#{name}.arl"
                if not archive.is_file():
                    continue
                found.add(name)
                index = len(records)
                extracted = scratch / f"extract-{index}"
                run_extract(tool, archive, extracted)
                original = {p.relative_to(extracted): p.read_bytes() for p in extracted.rglob("*") if p.is_file()}
                expected = dict(original)
                edits = []
                for relative, data in original.items():
                    if not str(relative).endswith(".set.xml"):
                        continue
                    modified, removed = remove_life_objects(data)
                    if removed:
                        expected[relative] = modified
                        (extracted / relative).write_bytes(modified)
                        edits.append({"file": str(relative), "removed": removed})
                record = {"archive": str(archive.relative_to(source)), "edits": edits,
                          "preserved_entries": len(original) - len(edits)}
                if edits:
                    packed = scratch / f"packed-{index}"
                    packed.mkdir()
                    subprocess.run([str(tool), str(extracted), str(packed / f"#{name}.ar"), "-P", "-T=ar"], check=True, capture_output=True)
                    verified = scratch / f"verify-{index}"
                    run_extract(tool, packed / archive.name, verified)
                    actual = {p.relative_to(verified): p.read_bytes() for p in verified.rglob("*") if p.is_file()}
                    if actual != expected:
                        raise ValueError(f"Archive round-trip changed an unexpected entry: {archive}")
                    new_files = list(packed.iterdir())
                    old_names = {p.name for p in directory.glob(f"#{name}.ar.*")} | {archive.name}
                    if {p.name for p in new_files} != old_names:
                        raise ValueError(f"Archive part layout changed: {archive}")
                    destination = output / directory.relative_to(source)
                    for file in new_files:
                        shutil.copy2(file, destination / file.name)
                    # Keep the review overlay consistent with the baked archives.
                    for edit in edits:
                        overlay = output / "mods/DayStageArcade/work" / name / edit["file"]
                        overlay.parent.mkdir(parents=True, exist_ok=True)
                        overlay.write_bytes(expected[Path(edit["file"])])
                records.append(record)
                print(f"Checked {name}: removed {sum(len(e['removed']) for e in edits)} life objects", flush=True)
                shutil.rmtree(extracted)
                if edits:
                    shutil.rmtree(verified)
                    shutil.rmtree(packed)
    if found != archives:
        raise ValueError(f"Missing stage archives: {archives-found}")
    manifest = {"stage_count": len(found), "removed_objects": sum(len(e["removed"]) for r in records for e in r["edits"]),
                "records": records, "normal_rings_and_energy_preserved": True}
    if not manifest["removed_objects"]:
        raise ValueError("No extra-life objects were found")
    (output / "ArcadeGameplayData-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(f"Verified {len(found)} stages; removed {manifest['removed_objects']} extra-life objects", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "output", "catalog", "tool"):
        parser.add_argument("--"+name, required=True, type=Path)
    args = parser.parse_args()
    refine(args.source, args.output, args.catalog, args.tool)
