"""Split and reconstruct large files with SHA-256 verification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BUFFER_SIZE = 8 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 1_900_000_000


def split_file(source: Path, output_dir: Path, prefix: str, chunk_size: int) -> Path:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise ValueError(f"Input file does not exist: {source}")
    if chunk_size <= 0 or chunk_size >= 2_000_000_000:
        raise ValueError("Chunk size must be between 1 and 1,999,999,999 bytes")

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{prefix}.manifest.json"
    existing = list(output_dir.glob(f"{prefix}.part*"))
    if manifest_path.exists() or existing:
        raise ValueError(f"Refusing to overwrite existing split output in {output_dir}")

    full_hash = hashlib.sha256()
    parts: list[dict[str, object]] = []
    total_size = 0

    with source.open("rb") as input_stream:
        index = 1
        while True:
            part_path = output_dir / f"{prefix}.part{index:03d}"
            part_hash = hashlib.sha256()
            part_size = 0

            with part_path.open("xb") as output_stream:
                while part_size < chunk_size:
                    block = input_stream.read(min(BUFFER_SIZE, chunk_size - part_size))
                    if not block:
                        break
                    output_stream.write(block)
                    part_hash.update(block)
                    full_hash.update(block)
                    part_size += len(block)
                    total_size += len(block)

            if part_size == 0:
                part_path.unlink()
                break

            parts.append({"name": part_path.name, "size": part_size, "sha256": part_hash.hexdigest()})
            index += 1

    manifest = {
        "original_name": source.name,
        "size": total_size,
        "sha256": full_hash.hexdigest(),
        "chunk_size": chunk_size,
        "parts": parts,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Split {source} into {len(parts)} verified parts")
    return manifest_path


def join_file(manifest_path: Path, parts_dir: Path, output: Path) -> None:
    manifest_path = manifest_path.resolve()
    parts_dir = parts_dir.resolve()
    output = output.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if output.exists():
        raise ValueError(f"Refusing to overwrite output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    full_hash = hashlib.sha256()
    total_size = 0
    try:
        with output.open("xb") as output_stream:
            for part in manifest["parts"]:
                part_path = parts_dir / part["name"]
                if not part_path.is_file():
                    raise ValueError(f"Missing part: {part_path}")
                if part_path.stat().st_size != part["size"]:
                    raise ValueError(f"Size mismatch: {part_path.name}")

                part_hash = hashlib.sha256()
                with part_path.open("rb") as part_stream:
                    while block := part_stream.read(BUFFER_SIZE):
                        output_stream.write(block)
                        part_hash.update(block)
                        full_hash.update(block)
                        total_size += len(block)

                if part_hash.hexdigest() != part["sha256"]:
                    raise ValueError(f"SHA-256 mismatch: {part_path.name}")

        if total_size != manifest["size"]:
            raise ValueError("Reconstructed file size does not match the manifest")
        if full_hash.hexdigest() != manifest["sha256"]:
            raise ValueError("Reconstructed file SHA-256 does not match the manifest")
    except BaseException:
        output.unlink(missing_ok=True)
        raise

    print(f"Reconstructed and verified {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    split_parser = subparsers.add_parser("split")
    split_parser.add_argument("--input", type=Path, required=True)
    split_parser.add_argument("--output-dir", type=Path, required=True)
    split_parser.add_argument("--prefix")
    split_parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)

    join_parser = subparsers.add_parser("join")
    join_parser.add_argument("--manifest", type=Path, required=True)
    join_parser.add_argument("--parts-dir", type=Path, required=True)
    join_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "split":
        prefix = args.prefix or args.input.name
        split_file(args.input, args.output_dir, prefix, args.chunk_size)
    else:
        join_file(args.manifest, args.parts_dir, args.output)


if __name__ == "__main__":
    main()
