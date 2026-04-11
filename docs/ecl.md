---
layout: default
title: ECLgraph
nav_order: 5
permalink: /ecl/
---

# ECLgraph (EGR) Format
{: .fs-8 }

64-bit edge binary CSR format from Texas State University
{: .fs-5 .fw-300 }

---

## Overview

ECLgraph is a **binary CSR (Compressed Sparse Row)** graph format designed for GPU graph algorithms. It was developed by **Martin Burtscher** at **Texas State University**.

Key characteristics:

- Uses **64-bit** (`long long`) for edge indices (`nindex`), allowing graphs with more than 2 billion edges
- Uses **32-bit** (`int`) for node IDs in adjacency lists (`nlist`), limiting to fewer than ~2 billion nodes
- Optional **32-bit integer** edge weights (`eweight`)
- Node IDs are **0-indexed**
- Common file extension: **`.egr`**

---

## C Struct Definition

The canonical in-memory representation from [`ECLgraph.h`](https://cs.txstate.edu/~burtscher/research/ECLgraph/):

```c
struct ECLgraph {
  long long nodes;     // number of nodes (< INT_MAX)
  long long edges;     // number of edges (can be > INT_MAX)
  long long* nindex;   // CSR offsets: array of size (nodes+1), 64-bit
  int* nlist;          // adjacency list: array of size edges, 32-bit
  int* eweight;        // edge weights: array of size edges (NULL if unweighted)
};
```

| Field      | Type         | Size per element | Count       | Description                        |
|:-----------|:-------------|:-----------------|:------------|:-----------------------------------|
| `nodes`    | `long long`  | 8 bytes          | 1           | Number of nodes                    |
| `edges`    | `long long`  | 8 bytes          | 1           | Number of edges                    |
| `nindex`   | `long long*` | 8 bytes          | `nodes + 1` | CSR offset array                   |
| `nlist`    | `int*`       | 4 bytes          | `edges`     | Destination node IDs               |
| `eweight`  | `int*`       | 4 bytes          | `edges`     | Edge weights (NULL if unweighted)  |

---

## Binary File Layout

An EGR file is a flat binary dump of the struct fields in order, with **no header byte** and **no magic number**:

```
Offset  0:                          [8 bytes]             nodes    (long long, little-endian)
Offset  8:                          [8 bytes]             edges    (long long, little-endian)
Offset 16:                          [(nodes+1) × 8 bytes] nindex  (long long[])
Offset 16 + (nodes+1)*8:           [edges × 4 bytes]     nlist   (int[])
(if weighted, immediately after):   [edges × 4 bytes]     eweight (int[])
```

**Key distinction from BGR:** The `nindex` (offset) array is **always 64-bit** and the `nlist` (adjacency) array is **always 32-bit**. There is no header byte to encode type widths — they are fixed.

---

## Detecting Weighted vs Unweighted

Since there is no header flag indicating whether weights are present, the reader determines this from the **file size**:

1. Read `nodes` and `edges` from the first 16 bytes.
2. Calculate the **expected unweighted size**:
   ```
   unweighted_size = 8 + 8 + (nodes + 1) * 8 + edges * 4
   ```
3. Calculate the **expected weighted size**:
   ```
   weighted_size = unweighted_size + edges * 4
   ```
4. Compare with the actual file size:
   - If file size equals `unweighted_size` → **no weights**
   - If file size equals `weighted_size` → **has weights**

The `readECLgraph` function in `ECLgraph.h` handles this by attempting to read `edges` weight values after the adjacency list. If `fread` returns 0 elements, the weight pointer is set to `NULL`.

---

## Example

A directed graph with **4 nodes** and **5 edges** (unweighted):

```
0 → 1, 2
1 → 2, 3
2 → 3
3 → (none)
```

**CSR arrays:**

| Array    | Values                       |
|:---------|:-----------------------------|
| `nodes`  | `4`                          |
| `edges`  | `5`                          |
| `nindex` | `[0, 2, 4, 5, 5]`           |
| `nlist`  | `[1, 2, 2, 3, 3]`           |

**Binary layout** (little-endian, 76 bytes total):

```
Offset  0: 04 00 00 00 00 00 00 00   ← nodes = 4
Offset  8: 05 00 00 00 00 00 00 00   ← edges = 5
Offset 16: 00 00 00 00 00 00 00 00   ← nindex[0] = 0
Offset 24: 02 00 00 00 00 00 00 00   ← nindex[1] = 2
Offset 32: 04 00 00 00 00 00 00 00   ← nindex[2] = 4
Offset 40: 05 00 00 00 00 00 00 00   ← nindex[3] = 5
Offset 48: 05 00 00 00 00 00 00 00   ← nindex[4] = 5
Offset 56: 01 00 00 00               ← nlist[0] = 1
Offset 60: 02 00 00 00               ← nlist[1] = 2
Offset 64: 02 00 00 00               ← nlist[2] = 2
Offset 68: 03 00 00 00               ← nlist[3] = 3
Offset 72: 03 00 00 00               ← nlist[4] = 3
```

Total file size: **76 bytes** = 8 + 8 + 5×8 + 5×4

---

## Reading EGR Files (C)

From [`ECLgraph.h`](https://cs.txstate.edu/~burtscher/research/ECLgraph/):

```c
ECLgraph readECLgraph(const char* const fname)
{
  ECLgraph g;
  int cnt;

  FILE* f = fopen(fname, "rb");
  if (f == NULL) {
    fprintf(stderr, "ERROR: could not open file %s\n\n", fname);
    exit(-1);
  }
  cnt = fread(&g.nodes, sizeof(g.nodes), 1, f);
  if (cnt != 1) { fprintf(stderr, "ERROR: failed to read nodes\n\n"); exit(-1); }
  cnt = fread(&g.edges, sizeof(g.edges), 1, f);
  if (cnt != 1) { fprintf(stderr, "ERROR: failed to read edges\n\n"); exit(-1); }
  if ((g.nodes < 1) || (g.edges < 0)) {
    fprintf(stderr, "ERROR: node or edge count too low\n\n"); exit(-1);
  }

  g.nindex = (long long*)malloc((g.nodes + 1) * sizeof(g.nindex[0]));
  g.nlist  = (int*)malloc((size_t)g.edges * sizeof(g.nlist[0]));
  g.eweight = (int*)malloc((size_t)g.edges * sizeof(g.eweight[0]));
  if ((g.nindex == NULL) || (g.nlist == NULL) || (g.eweight == NULL)) {
    fprintf(stderr, "ERROR: memory allocation failed\n\n"); exit(-1);
  }

  cnt = fread(g.nindex, sizeof(g.nindex[0]), g.nodes + 1, f);
  if (cnt != g.nodes + 1) {
    fprintf(stderr, "ERROR: failed to read neighbor index list\n\n"); exit(-1);
  }
  long long cnt1 = fread(g.nlist, sizeof(g.nlist[0]), (size_t)g.edges, f);
  if (cnt1 != g.edges) {
    fprintf(stderr, "ERROR: failed to read neighbor list\n\n"); exit(-1);
  }

  // Detect weights: attempt to read edge weights after adjacency list
  cnt = fread(g.eweight, sizeof(g.eweight[0]), (size_t)g.edges, f);
  if (cnt == 0) {
    free(g.eweight);
    g.eweight = NULL;  // unweighted graph
  } else if (cnt != g.edges) {
    fprintf(stderr, "ERROR: failed to read edge weights\n\n"); exit(-1);
  }

  fclose(f);
  return g;
}
```

**Simplified reading** (from [`egr-reader.cpp`](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters)):

```c
long long nodes, edges;
fread(&nodes, sizeof(long long), 1, fp);
fread(&edges, sizeof(long long), 1, fp);

long long* nindex = new long long[nodes + 1];
int* nlist = new int[edges];

fread(nindex, sizeof(long long), nodes + 1, fp);
fread(nlist, sizeof(int), edges, fp);
```

---

## Writing EGR Files (C)

From [`ECLgraph.h`](https://cs.txstate.edu/~burtscher/research/ECLgraph/):

```c
void writeECLgraph(const ECLgraph g, const char* const fname)
{
  if ((g.nodes < 1) || (g.edges < 0)) {
    fprintf(stderr, "ERROR: node or edge count too low\n\n"); exit(-1);
  }
  int cnt;
  FILE* f = fopen(fname, "wb");
  if (f == NULL) {
    fprintf(stderr, "ERROR: could not open file %s\n\n", fname); exit(-1);
  }

  cnt = fwrite(&g.nodes, sizeof(g.nodes), 1, f);
  if (cnt != 1) { fprintf(stderr, "ERROR: failed to write nodes\n\n"); exit(-1); }
  cnt = fwrite(&g.edges, sizeof(g.edges), 1, f);
  if (cnt != 1) { fprintf(stderr, "ERROR: failed to write edges\n\n"); exit(-1); }

  cnt = fwrite(g.nindex, sizeof(g.nindex[0]), g.nodes + 1, f);
  if (cnt != g.nodes + 1) {
    fprintf(stderr, "ERROR: failed to write neighbor index list\n\n"); exit(-1);
  }
  long long cnt1 = fwrite(g.nlist, sizeof(g.nlist[0]), (size_t)g.edges, f);
  if (cnt1 != g.edges) {
    fprintf(stderr, "ERROR: failed to write neighbor list\n\n"); exit(-1);
  }

  // Write weights only if present
  if (g.eweight != NULL) {
    cnt = fwrite(g.eweight, sizeof(g.eweight[0]), (size_t)g.edges, f);
    if (cnt != g.edges) {
      fprintf(stderr, "ERROR: failed to write edge weights\n\n"); exit(-1);
    }
  }

  fclose(f);
}
```

---

## Comparison with BGR

| Feature           | ECLgraph (EGR)          | BGR                        |
|:------------------|:------------------------|:---------------------------|
| **Header**        | None (implicit)         | 1-byte flags               |
| **Offset array**  | Always 64-bit           | Adaptive (32/64-bit)       |
| **Node IDs**      | Always 32-bit           | Adaptive (32/64-bit)       |
| **Max nodes**     | ~2B (`int`)             | ~2⁶⁴ (`uint64`)           |
| **Max edges**     | ~2⁶³ (`long long`)     | ~2⁶⁴ (`uint64`)           |
| **Weight detect** | By file size            | By header flag             |
| **Weight type**   | `int` (32-bit)          | `int` / `float` (by flag)  |
| **Origin**        | Texas State University  | HPC-HGA                   |

---

## Tools

The following converters and utilities are available in the [graph-format-converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters) repository:

| Tool | Description |
|:-----|:------------|
| `mtx-egr` | Convert MTX (Matrix Market) to ECLgraph format (symmetrized, unweighted) |
| `egr-single` | Convert symmetric EGR to directed (single edges) |
| `egr-reader` | Read and display the first edges of an EGR file |

---

## References

- **ECLgraph source:** [https://cs.txstate.edu/~burtscher/research/ECLgraph/](https://cs.txstate.edu/~burtscher/research/ECLgraph/)
- **Copyright:** Martin Burtscher, 2023 — BSD 3-Clause License
- **ECLgraph.h:** Header defining the struct, `readECLgraph`, `writeECLgraph`, and `freeECLgraph` functions
