---
layout: default
title: WGBin
nav_order: 6
permalink: /wgbin/
---

# WGBin (WebGraph Binary) Format
{: .fs-8 }

Intermediate binary split-file format for WebGraph conversion
{: .fs-5 .fw-300 }

---

## Overview

WGBin is a **legacy intermediate format** from an earlier BVGraph conversion pipeline. It splits graph data into three separate files — properties, offsets, and edges — enabling simple parallel I/O during conversion.

Key characteristics:

- **Three-file layout**: a text properties file, a binary offsets file, and a binary edges file
- **Variable byte width** for vertex IDs, computed as `ceil(log2(nodes) / 8)`
- **Designed for multi-threaded parallel writing** with per-partition work distribution
- **Node IDs are 0-indexed**
- **Native byte order** (little-endian on x86/ARM systems) for both offsets and edge data

{: .warning }
> This format is considered legacy. For new projects, prefer BGR or MTX format with direct conversion using `bvgraph_to_bgr` or `bvgraph_to_mtx`.

---

## File Components

A WGBin dataset consists of three files sharing a common basename:

| File | Description |
|:-----|:------------|
| `<name>_props.txt` | Text properties file: vertex count, edge count, bytes per vertex ID, companion file names |
| `<name>_offsets.bin` | Binary offsets: 8 bytes (int64) per vertex, giving the cumulative edge index for each node |
| `<name>_edges.bin` | Binary edge list: packed vertex IDs with variable byte width |

---

## Properties File

The properties file is a plain-text key-value file (one entry per line, colon-separated):

```
vertices-count:325557
edges-count:3216152
bytes-per-vertex-ID-in-edges-file:3
offsets-file:cnr-2000_offsets.bin
edges-file:cnr-2000_edges.bin
```

| Field | Description |
|:------|:------------|
| `vertices-count` | Total number of vertices (nodes) in the graph |
| `edges-count` | Total number of directed edges (arcs) in the graph |
| `bytes-per-vertex-ID-in-edges-file` | Number of bytes used to store each neighbor ID in the edges file (typically 3 or 4) |
| `offsets-file` | Filename of the binary offsets file |
| `edges-file` | Filename of the binary edges file |

---

## Offsets File

The offsets file is a binary file containing **`vertices-count + 1`** entries.

- Each entry is **8 bytes** (64-bit integer, native byte order)
- `offsets[i]` = cumulative edge count before node `i` (i.e., the starting index into the logical edge array)
- `offsets[vertices-count]` = total number of edges (`edges-count`)
- The byte position in the edges file for node `i`'s neighbor list is: `offsets[i] × bytes-per-vertex-ID`
- Total file size: `(vertices-count + 1) × 8` bytes

**Degree calculation:**

```
degree(i) = offsets[i + 1] − offsets[i]
```

---

## Edges File

The edges file is a binary file containing all adjacency lists packed sequentially.

- Each neighbor ID is stored using exactly **`bytes-per-vertex-ID`** bytes
- **Native byte order** (little-endian on x86/ARM); the writer uses Java's `ByteOrder.nativeOrder()` and the reader reconstructs IDs assuming little-endian layout
- Neighbors for node `i` occupy bytes from `offsets[i] × bytes-per-vertex-ID` to `offsets[i+1] × bytes-per-vertex-ID`
- Total file size: `edges-count × bytes-per-vertex-ID` bytes

**Number of neighbors for node `i`:**

```
neighbors(i) = (offsets[i + 1] − offsets[i])
```

---

## Variable Byte Width

The byte width for vertex IDs is computed to use the minimum number of whole bytes needed to represent any node ID in the graph:

```
bytes-per-vertex-ID = ceil(log2(vertices-count) / 8)
```

This yields:

| Vertex Count Range | Bits Needed | Bytes per ID |
|:-------------------|:------------|:-------------|
| ≤ 256 (2⁸) | ≤ 8 | 1 |
| ≤ 65,536 (2¹⁶) | ≤ 16 | 2 |
| ≤ 16,777,216 (2²⁴) | ≤ 24 | 3 |
| ≤ 4,294,967,296 (2³²) | ≤ 32 | 4 |

For most web graphs (millions of nodes), this results in **3 bytes per vertex ID**, saving ~25% space compared to always using 4-byte integers.

---

## Reading WGBin Files

The following pseudocode (based on [ReadWGBin.cpp](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/ReadWGBin.cpp)) shows how to read WGBin files:

```cpp
// 1. Parse properties file
int64_t vertices_count, edges_count;
int bytes_per_id;
parse_props("graph_props.txt", vertices_count, edges_count, bytes_per_id);

// 2. Read offsets (vertices_count + 1 entries, 8 bytes each)
vector<int64_t> offsets(vertices_count + 1);
ifstream off_file("graph_offsets.bin", ios::binary);
off_file.read(reinterpret_cast<char*>(offsets.data()),
              (vertices_count + 1) * sizeof(int64_t));

// 3. Read edges using offsets and byte width
vector<int> edges(edges_count);
// Memory-map the edges file for parallel access
char* edge_data = mmap_file("graph_edges.bin");

#pragma omp parallel for schedule(dynamic)
for (int64_t i = 0; i < vertices_count; i++) {
    for (int64_t j = offsets[i]; j < offsets[i + 1]; j++) {
        int64_t pos = j * bytes_per_id;
        int target = 0;
        for (int k = 0; k < bytes_per_id; k++) {
            target |= (static_cast<unsigned char>(edge_data[pos + k]) << (k * 8));
        }
        edges[j] = target;
    }
}
```

{: .note }
> The reader uses `mmap` and OpenMP for parallel edge decoding. The inner loop reconstructs each vertex ID from its individual bytes in little-endian order.

---

## Multi-Threaded Writing

The writer ([WG2Bin.java](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters/blob/main/WG2Bin.java)) uses a three-step parallel pipeline:

1. **Step 0 — Partition & count**: Vertices are divided evenly among threads. Each thread computes the total degree (edge count) for its partition. A prefix sum across thread totals produces global edge offsets.

2. **Step 1 — Write offsets**: Each thread writes its portion of the offsets file using memory-mapped I/O. The offset for each vertex is its global cumulative edge index.

3. **Step 2 — Write edges**: Partitions are further subdivided into jobs (bounded by a buffer size limit). Threads process jobs using a **work-stealing** strategy — after finishing their own jobs, idle threads pick up unfinished jobs from other threads.

The offsets and edges files are pre-allocated to their full size before writing, allowing threads to write to non-overlapping regions via `MappedByteBuffer`.

---

## Tools

| Tool | Language | Description |
|:-----|:---------|:------------|
| `WG2Bin` | Java | Convert BVGraph to WGBin format (multi-threaded) |
| `ReadWGBin` | C++ | Read WGBin and convert to ECLgraph/EGR format (OpenMP parallel) |

Both tools are available at: [github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters)
