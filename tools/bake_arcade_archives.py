"""Bake reviewed XML edits into copied archives, preserving all other entries."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_arcade_mod import run_extract


def bake(data: Path, overlay: Path, tool: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    shutil.copytree(overlay, output)
    work = overlay / "mods/DayStageArcade/work"
    records = []
    sources = [data / "game", *(data / "dlc").iterdir()]
    with tempfile.TemporaryDirectory(prefix="arcade-bake-") as temporary:
        scratch = Path(temporary)
        for edits in sorted(work.iterdir()):
            if not edits.is_dir():
                continue
            found = False
            for source in sources:
                archive = source / f"#{edits.name}.arl"
                if not archive.is_file():
                    continue
                found = True
                index = len(records)
                extracted = scratch / str(index)
                run_extract(tool, archive, extracted)
                originals = {p.relative_to(extracted): p.read_bytes()
                             for p in extracted.rglob("*") if p.is_file()}
                edits_map = {p.relative_to(edits): p for p in edits.rglob("*") if p.is_file()}
                for relative, edit in edits_map.items():
                    target = extracted / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(edit, target)
                destination = output / source.relative_to(data)
                destination.mkdir(parents=True, exist_ok=True)
                result = subprocess.run([str(tool), str(extracted),
                    str(destination / f"#{edits.name}.ar"), "-P", "-T=ar"],
                    capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                # Read the packed result back through the same retail archive
                # decoder and compare every member, including untouched assets.
                verified = scratch / f"verify-{index}"
                packed_list = destination / archive.name
                if not packed_list.exists():
                    raise ValueError(f"Archive packer did not generate {packed_list}")
                run_extract(tool, packed_list, verified)
                actual = {p.relative_to(verified): p.read_bytes()
                          for p in verified.rglob("*") if p.is_file()}
                expected = dict(originals)
                expected.update({p: edit.read_bytes() for p, edit in edits_map.items()})
                if actual != expected:
                    raise ValueError(f"Archive round-trip verification failed: {archive}")
                records.append({"archive": str(archive.relative_to(data)),
                                "preserved_entries": len(originals.keys() - edits_map.keys()),
                                "edited_entries": [str(p) for p in edits_map]})
            if not found:
                raise ValueError(f"No source archive found for {edits.name}")
    (output / "BakedArcadeArchives-manifest.json").write_text(json.dumps(records, indent=2)+"\n")
    print(f"Baked and round-trip verified {len(records)} archives: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("data-root", "overlay", "hedge-arc-pack", "output"):
        parser.add_argument("--"+option, type=Path, required=True)
    args = parser.parse_args()
    bake(args.data_root.resolve(), args.overlay.resolve(), args.hedge_arc_pack.resolve(), args.output.resolve())
