#!/usr/bin/env python3
"""Validate BGR v2 headers, file sizes, and optionally complete CSR contents."""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import struct
import sys
from typing import Optional


NODE_U64 = 0x01
EDGE_U64 = 0x02
WEIGHTED = 0x08
KNOWN_FLAGS = NODE_U64 | EDGE_U64 | WEIGHTED
CHUNK_BYTES = 8 * 1024 * 1024


class BGRFormatError(ValueError):
    """Raised when a file is not structurally valid BGR v2."""


@dataclass(frozen=True)
class BGRInfo:
    path: str
    flags: int
    nodes: int
    edges: int
    node_width: int
    offset_width: int
    weighted: bool
    header_bytes: int
    row_ends_offset: int
    destinations_offset: int
    weights_offset: Optional[int]
    expected_size: int
    actual_size: int

    def record(self, validation: str) -> dict:
        record = asdict(self)
        record.update(status="ok", format="BGR v2",
                      flags_hex=f"0x{self.flags:02x}",
                      node_bits=self.node_width * 8,
                      offset_bits=self.offset_width * 8,
                      validation=validation)
        return record


def read_exact(handle, size: int, section: str) -> bytes:
    data = handle.read(size)
    if len(data) != size:
        raise BGRFormatError(
            f"truncated {section}: expected {size} bytes, found {len(data)}")
    return data


def read_uint(handle, width: int, section: str) -> int:
    return int.from_bytes(read_exact(handle, width, section), "little")


def inspect_header(path: Path) -> BGRInfo:
    try:
        stat = path.stat()
    except OSError as error:
        raise BGRFormatError(f"cannot stat file: {error}") from error
    if not path.is_file():
        raise BGRFormatError("not a regular file")

    try:
        with path.open("rb") as handle:
            flags = read_exact(handle, 1, "flags")[0]
            unknown = flags & ~KNOWN_FLAGS
            if unknown:
                raise BGRFormatError(
                    f"unknown/reserved flag bits set: 0x{unknown:02x}")

            node_width = 8 if flags & NODE_U64 else 4
            offset_width = 8 if flags & EDGE_U64 else 4
            nodes = read_uint(handle, node_width, "node count")
            edges = read_uint(handle, offset_width, "edge count")
    except OSError as error:
        raise BGRFormatError(f"cannot read file: {error}") from error

    if nodes == 0:
        raise BGRFormatError("node count must be positive")

    header_bytes = 1 + node_width + offset_width
    row_ends_bytes = nodes * offset_width
    destinations_bytes = edges * node_width
    weights_bytes = edges * 4 if flags & WEIGHTED else 0
    expected_size = (
        header_bytes + row_ends_bytes + destinations_bytes + weights_bytes)
    if stat.st_size != expected_size:
        raise BGRFormatError(
            f"file size mismatch: expected {expected_size} bytes from the "
            f"header, found {stat.st_size}")

    destinations_offset = header_bytes + row_ends_bytes
    weights_offset = (destinations_offset + destinations_bytes
                      if flags & WEIGHTED else None)
    return BGRInfo(
        path=str(path.absolute()),
        flags=flags,
        nodes=nodes,
        edges=edges,
        node_width=node_width,
        offset_width=offset_width,
        weighted=bool(flags & WEIGHTED),
        header_bytes=header_bytes,
        row_ends_offset=header_bytes,
        destinations_offset=destinations_offset,
        weights_offset=weights_offset,
        expected_size=expected_size,
        actual_size=stat.st_size,
    )


def iter_uints(handle, count: int, width: int, section: str):
    unpacker = struct.Struct("<Q" if width == 8 else "<I")
    chunk_items = max(1, CHUNK_BYTES // width)
    index = 0
    while index < count:
        items = min(chunk_items, count - index)
        data = read_exact(handle, items * width, section)
        for (value,) in unpacker.iter_unpack(data):
            yield index, value
            index += 1


def consume_exact(handle, size: int, section: str) -> None:
    remaining = size
    while remaining:
        amount = min(CHUNK_BYTES, remaining)
        read_exact(handle, amount, section)
        remaining -= amount


def validate_full(path: Path, info: BGRInfo) -> None:
    try:
        with path.open("rb") as handle:
            handle.seek(info.row_ends_offset)
            previous = 0
            final = 0
            for row, value in iter_uints(
                    handle, info.nodes, info.offset_width, "row-end offsets"):
                if value < previous:
                    raise BGRFormatError(
                        f"row-end offsets decrease at row {row}: "
                        f"{value} < {previous}")
                if value > info.edges:
                    raise BGRFormatError(
                        f"row-end offset at row {row} exceeds M: "
                        f"{value} > {info.edges}")
                previous = value
                final = value

            if info.nodes and final != info.edges:
                raise BGRFormatError(
                    f"final row-end offset is {final}, expected M={info.edges}")
            for edge, destination in iter_uints(
                    handle, info.edges, info.node_width, "destinations"):
                if destination >= info.nodes:
                    raise BGRFormatError(
                        f"destination at edge {edge} is outside [0, N): "
                        f"{destination} >= {info.nodes}")

            if info.weighted:
                consume_exact(handle, info.edges * 4, "float32 weights")
            if handle.read(1):
                raise BGRFormatError("unexpected trailing data")
    except OSError as error:
        raise BGRFormatError(f"cannot fully validate file: {error}") from error


def collect_files(inputs: list[Path]) -> list[Path]:
    files = []
    seen = set()
    for source in inputs:
        source = source.expanduser()
        if source.is_dir():
            matches = []

            def onerror(error):
                raise BGRFormatError(
                    f"cannot traverse {source}: {error}") from error

            for base, _, names in os.walk(source, followlinks=False,
                                          onerror=onerror):
                matches.extend(Path(base) / name for name in names
                               if name.lower().endswith(".bgr"))
            matches.sort(key=lambda path: str(path))
            if not matches:
                raise BGRFormatError(f"no .bgr files found under {source}")
        elif source.is_file():
            matches = [source]
        else:
            raise BGRFormatError(f"input does not exist: {source}")

        for path in matches:
            key = str(path.absolute())
            if key not in seen:
                seen.add(key)
                files.append(path)
    return files


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", type=Path, nargs="+",
        help="BGR file or directory; directories are searched recursively")
    parser.add_argument(
        "--full", action="store_true",
        help="stream-validate all row ends and destinations")
    parser.add_argument(
        "--json", action="store_true",
        help="write one JSON object per file")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = arguments(argv)
    try:
        files = collect_files(args.paths)
    except BGRFormatError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    failures = 0
    for path in files:
        try:
            info = inspect_header(path)
            if args.full:
                validate_full(path, info)
            record = info.record("full" if args.full else "header-and-size")
            if args.json:
                print(json.dumps(record, sort_keys=True))
            else:
                print(
                    f"OK {path}: flags={record['flags_hex']} "
                    f"N={info.nodes} M={info.edges} "
                    f"node_ids=uint{record['node_bits']} "
                    f"offsets=uint{record['offset_bits']} "
                    f"weighted={'yes' if info.weighted else 'no'} "
                    f"validation={record['validation']}")
        except BGRFormatError as error:
            failures += 1
            if args.json:
                print(json.dumps({
                    "path": str(path.absolute()),
                    "status": "invalid",
                    "error": str(error),
                }, sort_keys=True))
            else:
                print(f"INVALID {path}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
