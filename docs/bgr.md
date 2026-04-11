---
layout: default
title: BGR
nav_order: 4
permalink: /bgr/
---

# BGR (Binary Graph Representation)
{: .fs-8 }

Compact binary CSR format with adaptive integer sizes
{: .fs-5 .fw-300 }

---

## Overview

BGR is a compact binary format that stores graphs in Compressed Sparse Row (CSR) layout with automatic integer width selection. It is designed for high-performance graph analytics on shared-memory systems.

Key characteristics:

- **Binary CSR** (Compressed Sparse Row) format — no text parsing overhead
- Supports both **weighted and unweighted** graphs
- **Adaptive integer sizes**: uses uint32 when possible, uint64 for large graphs (>2³² nodes or edges)
- **1-byte header** with bit flags for format detection
- Node IDs are **0-indexed** (first node is 0)
- Designed for parallel I/O with `pread()` / `pwrite()`
- Used by [SCC Analysis](https://github.com/HPC-Heterogeneous-Graph-Algorithms) and other HPC graph algorithm benchmarks

---

## File Layout

A BGR file consists of a fixed header followed by three (or four) contiguous arrays:

```
Offset 0:          [1 byte]               Header flags
Offset 1:          [N bytes]              num_nodes (uint32 or uint64)
Offset 1+N:        [E bytes]              num_edges (uint32 or uint64)
Offset 1+N+E:      [(num_nodes+1) × E]    row_ptr array
Offset ...:        [num_edges × N]         col_idx array
(if weighted):     [num_edges × W]         edge_weights array
```

Where:

| Symbol | Meaning |
|:-------|:--------|
| **N** | Integer size for node counts/IDs — 4 bytes (uint32) or 8 bytes (uint64) |
| **E** | Integer size for edge counts/indices — 4 bytes (uint32) or 8 bytes (uint64) |
| **W** | Weight size (format-dependent, typically 4 bytes float or 8 bytes double) |

All multi-byte integers are stored in **little-endian** byte order (native x86/x86-64).

---

## Header Byte

The first byte of the file encodes format flags as individual bits:

```
Bit:    7  6  5  4  3  2  1  0
        ── ── ── ── ── ── ── ──
        reserved        │  │  │
                        │  │  └─ weighted (0 = no, 1 = yes)
                        │  └──── node ID size (0 = uint32, 1 = uint64)
                        └─────── edge count size (0 = uint32, 1 = uint64)
```

| Bit | Mask | Name | Meaning |
|:----|:-----|:-----|:--------|
| 0 | `0x01` | `weighted` | `0` = unweighted graph, `1` = weighted graph |
| 1 | `0x02` | `large_ids` | `0` = uint32 node IDs, `1` = uint64 node IDs |
| 2 | `0x04` | `large_edges` | `0` = uint32 edge counts, `1` = uint64 edge counts |
| 3–7 | | reserved | Must be zero |

### Common header values

| Header | Nodes | Edges | Weighted | Description |
|:-------|:------|:------|:---------|:------------|
| `0x00` | uint32 | uint32 | No | Small unweighted graph (<4B nodes, <4B edges) |
| `0x02` | uint64 | uint32 | No | Large node count, few edges per node |
| `0x04` | uint32 | uint64 | No | Small node count, many edges (>4B) |
| `0x06` | uint64 | uint64 | No | Large graph (>4B nodes and edges) |
| `0x01` | uint32 | uint32 | Yes | Small weighted graph |
| `0x03` | uint64 | uint32 | Yes | Large weighted, few edges per node |
| `0x07` | uint64 | uint64 | Yes | Large weighted graph |

{: .note }
Integer sizes are selected automatically based on magnitude: uint64 is used when `num_nodes > 0xFFFFFFFF` or `num_edges > 0xFFFFFFFF`.

---

## CSR Layout

BGR uses Compressed Sparse Row (CSR) representation, which stores the adjacency structure of a graph in two arrays:

### row_ptr (row pointer array)

- Length: **num_nodes + 1** entries
- Each entry is an edge index (uint32 or uint64 based on the `large_edges` flag)
- `row_ptr[i]` = index into `col_idx` where node `i`'s neighbors begin
- `row_ptr[i+1] - row_ptr[i]` = out-degree of node `i`
- `row_ptr[0]` is always `0`
- `row_ptr[num_nodes]` equals `num_edges`

### col_idx (column index array)

- Length: **num_edges** entries
- Each entry is a node ID (uint32 or uint64 based on the `large_ids` flag)
- `col_idx[row_ptr[i] .. row_ptr[i+1]-1]` = sorted neighbor list of node `i`

### edge_weights (optional)

- Present only when the `weighted` flag is set (bit 0 of header)
- Length: **num_edges** entries
- Each entry is a weight value (size depends on implementation)
- `edge_weights[k]` corresponds to the edge `col_idx[k]`

### Diagram

```
row_ptr:  [ 0 | 2 | 3 | 5 | 6 ]      (num_nodes + 1 = 5 entries)
col_idx:  [ 1 | 2 | 0 | 2 | 3 | 1 ]  (num_edges = 6 entries)

Node 0: neighbors at col_idx[0..1] → {1, 2}
Node 1: neighbors at col_idx[2..2] → {0}
Node 2: neighbors at col_idx[3..4] → {2, 3}
Node 3: neighbors at col_idx[5..5] → {1}
```

---

## Example

Consider a small directed graph with **4 nodes** and **6 edges**:

```
0 → 1, 2
1 → 0
2 → 2, 3
3 → 1
```

### CSR arrays (0-indexed)

```
row_ptr = [0, 2, 3, 5, 6]
col_idx = [1, 2, 0, 2, 3, 1]
```

### BGR binary (hex dump, annotated)

Since num_nodes=4 and num_edges=6 (both fit in uint32), the header is `0x00`:

```
Offset  Hex                                  Meaning
------  -----------------------------------  ---------------------------
0x00    00                                   Header: uint32/uint32, unweighted
0x01    04 00 00 00                          num_nodes = 4
0x05    06 00 00 00                          num_edges = 6
0x09    00 00 00 00                          row_ptr[0] = 0
0x0D    02 00 00 00                          row_ptr[1] = 2
0x11    03 00 00 00                          row_ptr[2] = 3
0x15    05 00 00 00                          row_ptr[3] = 5
0x19    06 00 00 00                          row_ptr[4] = 6
0x1D    01 00 00 00                          col_idx[0] = 1  (node 0 → 1)
0x21    02 00 00 00                          col_idx[1] = 2  (node 0 → 2)
0x25    00 00 00 00                          col_idx[2] = 0  (node 1 → 0)
0x29    02 00 00 00                          col_idx[3] = 2  (node 2 → 2)
0x2D    03 00 00 00                          col_idx[4] = 3  (node 2 → 3)
0x31    01 00 00 00                          col_idx[5] = 1  (node 3 → 1)
```

Total file size: 1 + 4 + 4 + (5 × 4) + (6 × 4) = **53 bytes**

---

## Reading BGR Files (C++)

```cpp
#include <cstdio>
#include <cstdint>
#include <vector>

struct BGRGraph {
    uint64_t num_nodes;
    uint64_t num_edges;
    bool weighted;
    std::vector<uint64_t> row_ptr;
    std::vector<uint64_t> col_idx;
};

BGRGraph read_bgr(const char* filename) {
    BGRGraph g;
    FILE* fp = fopen(filename, "rb");

    // Read header
    uint8_t header;
    fread(&header, 1, 1, fp);
    g.weighted   = header & 0x01;
    bool large_ids  = header & 0x02;
    bool large_edges = header & 0x04;

    // Read num_nodes
    if (large_ids) {
        fread(&g.num_nodes, 8, 1, fp);
    } else {
        uint32_t n; fread(&n, 4, 1, fp);
        g.num_nodes = n;
    }

    // Read num_edges
    if (large_edges) {
        fread(&g.num_edges, 8, 1, fp);
    } else {
        uint32_t m; fread(&m, 4, 1, fp);
        g.num_edges = m;
    }

    // Read row_ptr: (num_nodes + 1) entries
    g.row_ptr.resize(g.num_nodes + 1);
    if (large_edges) {
        fread(g.row_ptr.data(), 8, g.num_nodes + 1, fp);
    } else {
        std::vector<uint32_t> buf(g.num_nodes + 1);
        fread(buf.data(), 4, g.num_nodes + 1, fp);
        for (uint64_t i = 0; i <= g.num_nodes; i++)
            g.row_ptr[i] = buf[i];
    }

    // Read col_idx: num_edges entries
    g.col_idx.resize(g.num_edges);
    if (large_ids) {
        fread(g.col_idx.data(), 8, g.num_edges, fp);
    } else {
        std::vector<uint32_t> buf(g.num_edges);
        fread(buf.data(), 4, g.num_edges, fp);
        for (uint64_t i = 0; i < g.num_edges; i++)
            g.col_idx[i] = buf[i];
    }

    fclose(fp);
    return g;
}
```

{: .note }
For large graphs, consider memory-mapping the file with `mmap()` and using `pread()` for parallel access instead of sequential `fread()`.

---

## Writing BGR Files

Pseudocode for writing a graph in CSR form to BGR:

```
function write_bgr(filename, num_nodes, num_edges, row_ptr, col_idx):
    large_ids  = (num_nodes > 0xFFFFFFFF)
    large_edges = (num_edges > 0xFFFFFFFF)

    header = 0x00
    if weighted:    header |= 0x01
    if large_ids:   header |= 0x02
    if large_edges: header |= 0x04

    open file for binary writing
    write header                              (1 byte)
    write num_nodes as uint32 or uint64       (4 or 8 bytes)
    write num_edges as uint32 or uint64       (4 or 8 bytes)
    write row_ptr[] as uint32[] or uint64[]   ((num_nodes+1) entries)
    write col_idx[] as uint32[] or uint64[]   (num_edges entries)
    if weighted:
        write edge_weights[]                  (num_edges entries)
    close file
```

{: .note }
For best write performance on large graphs, pre-allocate the file with `ftruncate()` and use parallel `pwrite()` calls to fill different sections concurrently.

---

## Performance Notes

- **No parsing overhead**: Binary format eliminates the text-to-integer conversion cost of MTX
- **Memory-mapped I/O**: The contiguous array layout enables `mmap()` for zero-copy access
- **Parallel I/O**: Known array offsets allow concurrent `pread()` / `pwrite()` across threads
- **Compact**: A uint32 BGR file uses 4 bytes per edge vs. ~8–12 bytes per edge in text MTX
- **Typical throughput**: 75–120 M edges/s for conversion from BVGraph (multi-threaded C++)

### File size comparison (indochina-2004: 7.4M nodes, 194M edges)

| Format | File size | Notes |
|:-------|----------:|:------|
| BVGraph (.graph) | ~110 MB | Compressed bitstream |
| BGR (.bgr) | ~785 MB | Binary CSR (uint32) |
| MTX (.mtx) | ~2.4 GB | Text edge list |

---

## Tools

Tools for converting to and from BGR format:

| Tool | Description | Language |
|:-----|:------------|:---------|
| **`bvgraph_to_bgr`** | Convert BVGraph to BGR (multi-threaded) | C++ |
| **`WG2BGR`** | Convert BVGraph to BGR (WebGraph library) | Java |
| **`bgr2scc`** | Convert BGR to algorithm-specific formats (for SCC benchmarking) | C++ |

All tools are available at: [github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters)
