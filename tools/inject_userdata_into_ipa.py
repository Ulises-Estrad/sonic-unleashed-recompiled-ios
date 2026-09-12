"""Inject local Unleashed game and save data into a compiled iOS IPA."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import zipfile


BUFFER_SIZE = 8 * 1024 * 1024
DIRECTORIES = ("game", "update", "dlc", "patched", "save")
REQUIRED_FILES = (
    "game/default.xex",
    "game/shader.ar",
    "update/default.xexp",
    "patched/default.xex",
    "save/SYS-DATA",
)
MANIFEST_NAME = "BundledGameData-manifest.json"
ZIP64_EXTRA_FIELD_ID = 0x0001


def validate_source(source: Path) -> None:
    for directory in DIRECTORIES:
        if not (source / directory).is_dir():
            raise ValueError(f"Missing directory: {source / directory}")
    for name in REQUIRED_FILES:
        if not (source / name).is_file():
            raise ValueError(f"Missing required file: {source / name}")


def app_prefix(archive: zipfile.ZipFile) -> str:
    candidates = set()
    for name in archive.namelist():
        parts = PurePosixPath(name).parts
        if len(parts) >= 2 and parts[0] == "Payload" and parts[1].endswith(".app"):
            candidates.add(f"Payload/{parts[1]}/")
    if len(candidates) != 1:
        raise ValueError(f"Expected one app bundle in IPA, found: {sorted(candidates)}")
    return next(iter(candidates))


def extra_field_ids(extra: bytes) -> set[int]:
    ids: set[int] = set()
    cursor = 0
    while cursor + 4 <= len(extra):
        field_id = int.from_bytes(extra[cursor : cursor + 2], "little")
        field_size = int.from_bytes(extra[cursor + 2 : cursor + 4], "little")
        cursor += 4
        if cursor + field_size > len(extra):
            raise ValueError("Malformed ZIP extra field")
        ids.add(field_id)
        cursor += field_size
    if cursor != len(extra):
        raise ValueError("Malformed ZIP extra-field trailer")
    return ids


def validate_ios_bundle(archive: zipfile.ZipFile) -> str:
    prefix = app_prefix(archive)
    plist_name = prefix + "Info.plist"
    try:
        info = plistlib.loads(archive.read(plist_name))
    except KeyError as error:
        raise ValueError(f"IPA is missing {plist_name}") from error
    except plistlib.InvalidFileException as error:
        raise ValueError(f"IPA has an invalid {plist_name}") from error

    executable = info.get("CFBundleExecutable")
    if not isinstance(executable, str) or not executable:
        raise ValueError("Info.plist has no valid CFBundleExecutable")
    executable_name = prefix + executable
    try:
        executable_info = archive.getinfo(executable_name)
    except KeyError as error:
        raise ValueError(
            f"IPA is missing its declared executable: {executable_name}"
        ) from error
    if executable_info.is_dir() or executable_info.file_size == 0:
        raise ValueError(f"IPA executable is empty: {executable_name}")
    return prefix


def validate_standard_zip(ipa: Path) -> None:
    """Reject ZIP64 because Sideloadly reports these huge IPAs as invalid apps."""

    if ipa.stat().st_size >= zipfile.ZIP64_LIMIT:
        raise ValueError(
            f"IPA is {ipa.stat().st_size} bytes; a Sideloadly-safe standard ZIP "
            f"must remain below {zipfile.ZIP64_LIMIT} bytes"
        )
    with zipfile.ZipFile(ipa, "r") as archive:
        validate_ios_bundle(archive)
        if archive.start_dir >= zipfile.ZIP64_LIMIT:
            raise ValueError("IPA central directory requires ZIP64")
        for info in archive.infolist():
            if ZIP64_EXTRA_FIELD_ID in extra_field_ids(info.extra):
                raise ValueError(f"IPA contains a ZIP64 entry: {info.filename}")
            if max(info.file_size, info.compress_size, info.header_offset) >= zipfile.ZIP64_LIMIT:
                raise ValueError(f"IPA entry exceeds standard-ZIP limits: {info.filename}")


def copy_zip_entry(source: zipfile.ZipFile, destination: zipfile.ZipFile, info: zipfile.ZipInfo) -> None:
    copied_info = copy.copy(info)
    if info.is_dir():
        destination.writestr(copied_info, b"")
        return
    with source.open(info, "r") as input_stream, destination.open(
        copied_info, "w"
    ) as output_stream:
        shutil.copyfileobj(input_stream, output_stream, BUFFER_SIZE)


def add_data_file(
    archive: zipfile.ZipFile,
    source_file: Path,
    archive_name: str,
    compression_level: int,
) -> str:
    info = zipfile.ZipInfo.from_file(source_file, arcname=archive_name)
    info.compress_type = zipfile.ZIP_DEFLATED
    info._compresslevel = compression_level
    digest = hashlib.sha256()
    with source_file.open("rb") as input_stream, archive.open(
        info, "w"
    ) as output_stream:
        while block := input_stream.read(BUFFER_SIZE):
            output_stream.write(block)
            digest.update(block)
    return digest.hexdigest()


def inject(compiled_ipa: Path, data_root: Path, output_ipa: Path, compression_level: int) -> None:
    compiled_ipa = compiled_ipa.resolve()
    data_root = data_root.resolve()
    output_ipa = output_ipa.resolve()

    if not compiled_ipa.is_file():
        raise ValueError(f"Compiled IPA does not exist: {compiled_ipa}")
    if output_ipa.exists():
        raise ValueError(f"Refusing to overwrite output: {output_ipa}")
    if not 0 <= compression_level <= 9:
        raise ValueError("Compression level must be between 0 and 9")
    validate_source(data_root)
    validate_standard_zip(compiled_ipa)
    output_ipa.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, str] = {}
    total_bytes = 0
    try:
        with zipfile.ZipFile(compiled_ipa, "r") as source_archive:
            prefix = validate_ios_bundle(source_archive)
            excluded_prefixes = (prefix + "GameData/", prefix + "_CodeSignature/")
            excluded_files = {
                prefix + MANIFEST_NAME,
                prefix + "CodeResources",
                prefix + "embedded.mobileprovision",
            }

            with zipfile.ZipFile(
                output_ipa,
                "x",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=compression_level,
                allowZip64=False,
            ) as output_archive:
                for info in source_archive.infolist():
                    if info.filename in excluded_files or info.filename.startswith(excluded_prefixes):
                        continue
                    copy_zip_entry(source_archive, output_archive, info)

                # Include the complete prepared root, not just the five retail
                # directories. The arcade overlay lives beside them as
                # cpkredir.ini, ModsDB.ini and mods/DayStageArcade/.
                files = sorted(path for path in data_root.rglob("*") if path.is_file())
                for source_file in files:
                    relative = source_file.relative_to(data_root).as_posix()
                    archive_name = prefix + "GameData/" + relative
                    manifest[relative] = add_data_file(
                        output_archive,
                        source_file,
                        archive_name,
                        compression_level,
                    )
                    total_bytes += source_file.stat().st_size

                if not manifest:
                    raise ValueError("No user data was added to the IPA")
                manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
                output_archive.writestr(prefix + MANIFEST_NAME, manifest_bytes)
    except BaseException:
        output_ipa.unlink(missing_ok=True)
        raise

    validate_standard_zip(output_ipa)
    print(f"Created {output_ipa} with {len(manifest)} bundled files ({total_bytes} bytes)")


def verify(ipa: Path) -> None:
    ipa = ipa.resolve()
    validate_standard_zip(ipa)
    with zipfile.ZipFile(ipa, "r") as archive:
        prefix = validate_ios_bundle(archive)
        manifest = json.loads(archive.read(prefix + MANIFEST_NAME))
        for required in REQUIRED_FILES:
            if required not in manifest:
                raise ValueError(f"Manifest is missing required file: {required}")
        for name, expected in manifest.items():
            digest = hashlib.sha256()
            with archive.open(prefix + "GameData/" + name) as stream:
                while block := stream.read(BUFFER_SIZE):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError(f"Bundled-data SHA-256 mismatch: {name}")
        corrupt = archive.testzip()
        if corrupt is not None:
            raise ValueError(f"Corrupt IPA entry: {corrupt}")
    print(f"Verified {ipa}: {len(manifest)} bundled files match the manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled-ipa", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compression-level", type=int, default=1)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()

    if args.verify:
        verify(args.verify)
    elif args.compiled_ipa and args.data_root and args.output:
        inject(args.compiled_ipa, args.data_root, args.output, args.compression_level)
        verify(args.output)
    else:
        parser.error("Use --compiled-ipa, --data-root, and --output; or use --verify")


if __name__ == "__main__":
    main()
