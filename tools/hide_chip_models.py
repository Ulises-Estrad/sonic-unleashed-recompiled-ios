"""Hide Chip's rendered geometry while retaining his animated skeleton."""

from pathlib import Path
import struct


def hide_chip_model(source: Path, destination: Path, version: int) -> None:
    data = bytearray(source.read_bytes())
    size, actual_version, payload_size, base, relocation = struct.unpack_from(">5I", data)
    if size != len(data) or actual_version != version or base != 24 or relocation != base + payload_size:
        raise ValueError(f"Unexpected Mirage model header: {source}")

    def word(offset: int) -> int:
        if not 0 <= offset <= payload_size - 4:
            raise ValueError(f"Invalid Mirage model offset in {source}: {offset}")
        return struct.unpack_from(">I", data, base + offset)[0]

    def pointers(offset: int) -> list[int]:
        count, start = word(offset), word(offset + 4)
        if count > (payload_size - start) // 4:
            raise ValueError(f"Invalid Mirage model array in {source}")
        return [word(start + index * 4) for index in range(count)]

    if version == 5:
        groups = pointers(0)
        if any(word(group + 24) for group in groups):
            raise ValueError(f"Unexpected special meshes in {source}")
    else:
        # The v4 fur model stores the three slots directly in its header.
        groups = [0]

    meshes = [mesh for group in groups for slot in (0, 8, 16) for mesh in pointers(group + slot)]
    if len(meshes) != {4: 8, 5: 11}[version]:
        raise ValueError(f"Unexpected number of Chip meshes in {source}")

    for mesh in meshes:
        material = base + word(mesh)
        if not data[material:material + 5] == b"whip_":
            raise ValueError(f"Unexpected material in {source}")
        count, offset, vertex_count = word(mesh + 4), word(mesh + 8), word(mesh + 12)
        if not 0 < count <= (payload_size - offset) // 2 or not vertex_count:
            raise ValueError(f"Invalid Chip mesh indices in {source}")
        for index in range(count):
            entry = base + offset + index * 2
            vertex = struct.unpack_from(">H", data, entry)[0]
            if vertex == 0xffff:
                continue  # Preserve the triangle-strip restart marker.
            if vertex >= vertex_count:
                raise ValueError(f"Invalid Chip vertex index in {source}")
            # Each triangle now uses the same vertex and has zero area.
            struct.pack_into(">H", data, entry, 0)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def hide_chip_models(extracted: Path, output: Path) -> None:
    for name, version in (("WhipRoot.model", 5), ("WhipRoot_fur.model", 4)):
        hide_chip_model(extracted / name, output / name, version)
