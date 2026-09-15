import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools/check_bgr.py"
SPEC = importlib.util.spec_from_file_location("check_bgr", CHECKER)
CHECK_BGR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CHECK_BGR
SPEC.loader.exec_module(CHECK_BGR)


def bgr_bytes(flags=0, nodes=3, row_ends=(1, 2, 3),
              destinations=(1, 2, 0), weights=None):
    node_width = 8 if flags & CHECK_BGR.NODE_U64 else 4
    offset_width = 8 if flags & CHECK_BGR.EDGE_U64 else 4
    data = bytes([flags])
    data += nodes.to_bytes(node_width, "little")
    data += len(destinations).to_bytes(offset_width, "little")
    data += b"".join(value.to_bytes(offset_width, "little")
                     for value in row_ends)
    data += b"".join(value.to_bytes(node_width, "little")
                     for value in destinations)
    if flags & CHECK_BGR.WEIGHTED:
        values = weights if weights is not None else [1.0] * len(destinations)
        data += struct.pack("<" + "f" * len(values), *values)
    return data


class BGRCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bgr-checker-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.graph = self.root / "graph.bgr"

    def run_checker(self, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(CHECKER), *map(str, arguments)],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, expected,
                         result.stdout + result.stderr)
        return result

    def test_all_defined_flag_variants_pass_full_validation(self):
        for widths in range(4):
            for weighted in (False, True):
                flags = widths | (CHECK_BGR.WEIGHTED if weighted else 0)
                with self.subTest(flags=flags):
                    self.graph.write_bytes(bgr_bytes(flags=flags))
                    info = CHECK_BGR.inspect_header(self.graph)
                    CHECK_BGR.validate_full(self.graph, info)
                    self.assertEqual(info.flags, flags)
                    self.assertEqual(info.weighted, weighted)

    def test_header_and_json_cli(self):
        self.graph.write_bytes(bgr_bytes(flags=CHECK_BGR.EDGE_U64))
        result = self.run_checker("--json", self.graph)
        record = json.loads(result.stdout)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["format"], "BGR v2")
        self.assertEqual(record["flags_hex"], "0x02")
        self.assertEqual(record["node_bits"], 32)
        self.assertEqual(record["offset_bits"], 64)
        self.assertEqual(record["validation"], "header-and-size")

    def test_directory_discovery_is_recursive_and_deduplicated(self):
        nested = self.root / "nested"
        nested.mkdir()
        second = nested / "second.bgr"
        self.graph.write_bytes(bgr_bytes())
        second.write_bytes(bgr_bytes())
        result = self.run_checker(self.root, self.graph)
        self.assertEqual(result.stdout.count("OK "), 2)

    def test_reserved_flags_are_rejected(self):
        self.graph.write_bytes(bgr_bytes(flags=0x04))
        result = self.run_checker(self.graph, expected=1)
        self.assertIn("unknown/reserved flag bits", result.stderr)

    def test_zero_node_graph_is_rejected(self):
        self.graph.write_bytes(bgr_bytes(
            nodes=0, row_ends=(), destinations=()))
        result = self.run_checker(self.graph, expected=1)
        self.assertIn("node count must be positive", result.stderr)

    def test_wrong_size_and_old_n_plus_one_layout_are_rejected(self):
        self.graph.write_bytes(bgr_bytes() + struct.pack("<I", 0))
        result = self.run_checker(self.graph, expected=1)
        self.assertIn("file size mismatch", result.stderr)

    def test_full_validation_rejects_bad_row_ends(self):
        cases = (
            ((2, 1, 3), "decrease"),
            ((1, 2, 4), "exceeds M"),
            ((1, 2, 2), "final row-end"),
        )
        for row_ends, message in cases:
            with self.subTest(row_ends=row_ends):
                self.graph.write_bytes(bgr_bytes(row_ends=row_ends))
                result = self.run_checker("--full", self.graph, expected=1)
                self.assertIn(message, result.stderr)

    def test_full_validation_rejects_out_of_range_destination(self):
        self.graph.write_bytes(
            bgr_bytes(destinations=(1, 3, 0)))
        result = self.run_checker("--full", self.graph, expected=1)
        self.assertIn("destination at edge 1", result.stderr)

    def test_weighted_payload_is_exactly_float32_per_edge(self):
        self.graph.write_bytes(
            bgr_bytes(flags=CHECK_BGR.WEIGHTED, weights=(1.0, 2.0, 3.0)))
        self.run_checker("--full", self.graph)
        self.graph.write_bytes(self.graph.read_bytes()[:-1])
        result = self.run_checker(self.graph, expected=1)
        self.assertIn("file size mismatch", result.stderr)

    def test_documented_example_is_49_bytes_and_valid(self):
        data = bgr_bytes(
            nodes=4,
            row_ends=(2, 3, 5, 6),
            destinations=(1, 2, 0, 2, 3, 1),
        )
        self.assertEqual(len(data), 49)
        self.graph.write_bytes(data)
        self.run_checker("--full", self.graph)


if __name__ == "__main__":
    unittest.main()
