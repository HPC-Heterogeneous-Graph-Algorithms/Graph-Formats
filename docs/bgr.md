---
layout: default
title: BGR
nav_order: 4
permalink: /bgr/
---

# BGR v2 (Binary Graph Representation)
{: .fs-8 }

Compact binary CSR format with adaptive integer widths
{: .fs-5 .fw-300 }

---

## Overview

BGR v2 stores a directed graph in Compressed Sparse Row (CSR) order. It uses a
one-byte flag field, little-endian integers, N cumulative row-end offsets, M
destination IDs, and optional float32 edge weights.

Key characteristics:

- Binary CSR with no text parsing overhead
- Zero-indexed node IDs
- 32-bit or 64-bit node IDs, selected by a flag
- 32-bit or 64-bit edge counts and offsets, selected independently
- Weighted and unweighted variants
- Contiguous arrays suitable for `pread()`, `pwrite()`, and memory mapping

{: .warning }
> BGR has no magic string or explicit version field. A `.bgr` extension alone
> does not prove compatibility. Validate files with the checker described below.

This specification matches the
[`bvgraph_to_bgr.cpp`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/bvgraph_to_bgr.cpp)
and
[`WG2BGR.java`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/WG2BGR.java)
converters and the PHEM BGR datasets.

---

## File Layout

A BGR file contains a header followed by two or three contiguous arrays:

```text
Offset 0:                         1 byte        flags
Offset 1:                         node_width    num_nodes
Offset 1 + node_width:            offset_width  num_edges
Offset header_bytes:              N * offset_width
                                                cumulative row-end offsets
Offset header_bytes
     + N * offset_width:          M * node_width
                                                destination node IDs
If weighted, final section:       M * 4 bytes   float32 edge weights
```

Definitions:

| Name | Meaning |
|:-----|:--------|
| `N` | Number of nodes |
| `M` | Number of directed edges |
| `node_width` | 4 bytes for uint32 or 8 bytes for uint64 |
| `offset_width` | 4 bytes for uint32 or 8 bytes for uint64 |
| `header_bytes` | `1 + node_width + offset_width` |

The exact file size is:

```text
1 + node_width + offset_width
  + N * offset_width
  + M * node_width
  + (weighted ? M * 4 : 0)
```

There is no padding between fields or arrays. All integers and float32 weights
are little-endian.

---

## Header Flags

```text
Bit:    7  6  5  4  3  2  1  0
        -- -- -- -- -- -- -- --
        reserved   W  R  E  N
```

| Bit | Mask | Name | Meaning |
|:----|:-----|:-----|:--------|
| 0 | `0x01` | `node_u64` | N and destination IDs are uint64 |
| 1 | `0x02` | `edge_u64` | M and row-end offsets are uint64 |
| 2 | `0x04` | reserved | Must be zero |
| 3 | `0x08` | `weighted` | M float32 weights follow destinations |
| 4-7 | `0xf0` | reserved | Must be zero |

Only masks `0x01`, `0x02`, and `0x08` are defined. A strict reader must reject
files with any other flag bit set.

### Common flag values

| Flags | Node IDs | Edge offsets | Weights |
|:------|:---------|:-------------|:--------|
| `0x00` | uint32 | uint32 | No |
| `0x01` | uint64 | uint32 | No |
| `0x02` | uint32 | uint64 | No |
| `0x03` | uint64 | uint64 | No |
| `0x08` | uint32 | uint32 | float32 |
| `0x09` | uint64 | uint32 | float32 |
| `0x0a` | uint32 | uint64 | float32 |
| `0x0b` | uint64 | uint64 | float32 |

Writers normally set `node_u64` when N cannot be represented as uint32 and set
`edge_u64` when M cannot be represented as uint32.

---

## CSR Representation

In memory, a conventional CSR row pointer has N + 1 values:

```text
row_ptr = [0, row_end_0, row_end_1, ..., row_end_(N-1)]
```

BGR does not store the leading zero. It stores exactly N cumulative row ends:

```text
stored_row_ends = [row_ptr[1], row_ptr[2], ..., row_ptr[N]]
```

A reader reconstructs the full row pointer by prepending zero.

Required invariants:

- N is positive.
- Row ends are nondecreasing.
- Every row end is in `[0, M]`.
- For N > 0, the final row end equals M.
- Every destination ID is in `[0, N)`.

The neighbors of node `u` occupy:

```text
col_idx[row_ptr[u] : row_ptr[u + 1]]
```

If weights are present, `weights[k]` belongs to `col_idx[k]`.

---

## Example

Consider a graph with four nodes and six edges:

```text
0 -> 1, 2
1 -> 0
2 -> 2, 3
3 -> 1
```

The conventional CSR arrays are:

```text
row_ptr = [0, 2, 3, 5, 6]
col_idx = [1, 2, 0, 2, 3, 1]
```

BGR stores only:

```text
row_ends = [2, 3, 5, 6]
col_idx  = [1, 2, 0, 2, 3, 1]
```

Both counts fit uint32 and the graph is unweighted, so flags are `0x00`:

```text
Offset  Hex                                  Meaning
------  -----------------------------------  ---------------------------
0x00    00                                   flags = 0x00
0x01    04 00 00 00                          N = 4
0x05    06 00 00 00                          M = 6
0x09    02 00 00 00                          row_end[0] = 2
0x0d    03 00 00 00                          row_end[1] = 3
0x11    05 00 00 00                          row_end[2] = 5
0x15    06 00 00 00                          row_end[3] = 6
0x19    01 00 00 00                          col_idx[0] = 1
0x1d    02 00 00 00                          col_idx[1] = 2
0x21    00 00 00 00                          col_idx[2] = 0
0x25    02 00 00 00                          col_idx[3] = 2
0x29    03 00 00 00                          col_idx[4] = 3
0x2d    01 00 00 00                          col_idx[5] = 1
```

Total size:

```text
1 + 4 + 4 + (4 * 4) + (6 * 4) = 49 bytes
```

---

## Reading BGR

The following pseudocode shows the required reconstruction:

```text
flags = read_uint8()
reject flags if flags & ~0x0b != 0

node_width   = 8 if flags & 0x01 else 4
offset_width = 8 if flags & 0x02 else 4
weighted     = flags & 0x08

N = read_little_endian_uint(node_width)
M = read_little_endian_uint(offset_width)

row_ptr = array(N + 1)
row_ptr[0] = 0
read row_ptr[1..N] using offset_width

col_idx = read M integers using node_width

if weighted:
    weights = read M little-endian float32 values
```

Readers must verify the exact file size before allocating from untrusted header
values, then validate the CSR invariants above.

---

## Writing BGR

```text
node_u64 = N > 0xffffffff
edge_u64 = M > 0xffffffff

flags = 0
if node_u64: flags |= 0x01
if edge_u64: flags |= 0x02
if weighted: flags |= 0x08

write flags
write N using node_width
write M using offset_width
write row_ptr[1..N] using offset_width
write col_idx[0..M-1] using node_width
if weighted:
    write weights[0..M-1] as float32
```

---

## Format Checker

This repository includes a zero-dependency Python checker:

```bash
# Fast: validate flags, counts, integer widths, and exact file size.
python3 tools/check_bgr.py graph.bgr

# Full: additionally stream-validate every row end and destination.
python3 tools/check_bgr.py --full graph.bgr

# Recursively check every .bgr under one or more directories.
python3 tools/check_bgr.py /path/to/graphs /another/path

# Machine-readable JSON Lines output.
python3 tools/check_bgr.py --json --full graph.bgr
```

The default header/size check is suitable for very large datasets. `--full`
reads the complete CSR and can take as long as reading the entire graph.

---

## Tools

| Tool | Description |
|:-----|:------------|
| [`tools/check_bgr.py`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/Graph-Formats/blob/main/tools/check_bgr.py) | Validate BGR v2 files |
| [`bvgraph_to_bgr`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/bvgraph_to_bgr.cpp) | Multi-threaded C++ BVGraph-to-BGR converter |
| [`WG2BGR`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/WG2BGR.java) | Java WebGraph-to-BGR converter |
