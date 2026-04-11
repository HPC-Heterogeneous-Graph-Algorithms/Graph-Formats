---
layout: default
title: MTX
nav_order: 3
permalink: /mtx/
---

# MTX (Matrix Market) Format
{: .fs-8 }

Standard text-based sparse matrix format for graph edge lists
{: .fs-5 .fw-300 }

---

## Overview

The Matrix Market (MTX) format is a standard developed by [NIST](https://www.nist.gov/) (National Institute of Standards and Technology) for exchanging sparse matrix data. In the context of graph processing, each non-zero entry represents an edge.

Key characteristics:

- **Human-readable** text format — easy to inspect, debug, and generate
- Each line represents one edge (source → destination)
- Node IDs are **1-indexed** (first node is 1, not 0)
- Optional edge weights (unweighted graphs use the `pattern` field type)
- Widely supported by graph libraries, linear algebra tools, and visualization software

---

## File Structure

An MTX file consists of three parts: a header line, optional comments, a size line, and edge entries.

```
%%MatrixMarket matrix coordinate pattern general
% Optional comment lines
% (lines starting with % are ignored)
<rows> <columns> <non-zeros>
<row_i> <col_j>
<row_i> <col_j>
...
```

| Section | Description |
|:--------|:------------|
| **Header line** | Starts with `%%MatrixMarket`, defines the format and data type |
| **Comment lines** | Lines starting with `%` — ignored by parsers |
| **Size line** | First non-comment line: dimensions and entry count |
| **Edge entries** | One edge per line, tab or space separated |

---

## Header Line

The header line declares the format of the file:

```
%%MatrixMarket matrix coordinate pattern general
```

| Component | Value | Description |
|:----------|:------|:------------|
| **Object** | `matrix` | Always `matrix` for graph data |
| **Format** | `coordinate` | Sparse format (one entry per line). The alternative `array` is for dense matrices and not used for graphs. |
| **Field** | `pattern` | Data type of entries — see below |
| **Symmetry** | `general` | Symmetry structure — see below |

### Field types

| Field | Description | Entry format |
|:------|:------------|:-------------|
| `pattern` | Unweighted graph — no values, only structure | `<src> <dst>` |
| `real` | Floating-point edge weights | `<src> <dst> <weight>` |
| `integer` | Integer edge weights | `<src> <dst> <weight>` |
| `complex` | Complex-valued entries (rare for graphs) | `<src> <dst> <real> <imag>` |

### Symmetry types

| Symmetry | Description |
|:---------|:------------|
| `general` | No symmetry assumed — directed graph. All edges are explicitly listed. |
| `symmetric` | Undirected graph — only the lower triangle is stored. Each entry `(i, j)` with `i ≥ j` implies the reverse edge `(j, i)`. |
| `skew-symmetric` | Anti-symmetric matrix (rare for graphs) |
| `hermitian` | Hermitian symmetry (complex-valued, rare for graphs) |

---

## Size Line

The first non-comment line after the header specifies the matrix dimensions and number of entries:

```
<num_rows> <num_columns> <num_non_zeros>
```

For graphs:

| Field | Meaning |
|:------|:--------|
| `num_rows` | Number of nodes |
| `num_columns` | Number of nodes (same as `num_rows` for graphs) |
| `num_non_zeros` | Number of edges (directed) or lower-triangle entries (symmetric) |

All values are positive integers. For a graph with _N_ nodes and _M_ edges: `N N M`.

---

## Edge Entries

After the size line, each subsequent line defines one edge:

```
<source> <destination>              (pattern — unweighted)
<source> <destination> <weight>     (real or integer — weighted)
```

Rules:

- **1-indexed**: The minimum valid ID is `1`, and the maximum is the number of nodes
- **Tab or space** separated
- **No particular ordering** is required, but edges are typically sorted by source then destination
- **Self-loops** are allowed (`source = destination`)
- **Duplicate edges** are allowed by the format but should be avoided for graphs

---

## Example

A directed graph with 5 nodes and 7 edges:

```
%%MatrixMarket matrix coordinate pattern general
% Example directed graph with 5 nodes and 7 edges
5 5 7
1	2
1	3
2	4
3	4
3	5
4	5
5	1
```

This represents the following graph:

```
1 → 2
1 → 3
2 → 4
3 → 4
3 → 5
4 → 5
5 → 1    (back edge, creates a cycle)
```

Node 1 has out-degree 2, node 3 has out-degree 2, and node 5 connects back to node 1 forming a cycle.

---

## Reading MTX Files

Pseudocode for reading an MTX file into an edge list (C/C++ style):

```cpp
FILE* f = fopen("graph.mtx", "r");

// Skip the header line
char line[256];
fgets(line, sizeof(line), f);  // %%MatrixMarket ...

// Skip comment lines (lines starting with '%')
while (fgets(line, sizeof(line), f)) {
    if (line[0] != '%') break;
}

// Parse the size line
long long nodes, cols, edges;
sscanf(line, "%lld %lld %lld", &nodes, &cols, &edges);

// Read edges
for (long long i = 0; i < edges; i++) {
    int src, dst;
    fscanf(f, "%d %d", &src, &dst);

    // Convert from 1-indexed to 0-indexed if needed
    int u = src - 1;
    int v = dst - 1;
    // store edge (u, v)
}

fclose(f);
```

{: .note }
When reading weighted MTX files, parse the additional weight field: `fscanf(f, "%d %d %d", &src, &dst, &weight)` for integer weights, or use `%lf` for real-valued weights.

---

## Writing MTX Files

Pseudocode for writing a graph to MTX format (C/C++ style):

```cpp
FILE* f = fopen("graph.mtx", "w");

// Write header
fprintf(f, "%%%%MatrixMarket matrix coordinate pattern general\n");

// Write size line: nodes, nodes, edges
fprintf(f, "%lld %lld %lld\n", num_nodes, num_nodes, num_edges);

// Write edges (convert 0-indexed to 1-indexed)
for (each edge (u, v) in graph) {
    fprintf(f, "%d\t%d\n", u + 1, v + 1);
}

fclose(f);
```

{: .note }
The `%%` in the header must be literal percent signs. In C `fprintf`, use `%%%%` to produce `%%` in the output.

---

## Variants

Common MTX variants encountered in graph processing:

| Variant | Header | Use case |
|:--------|:-------|:---------|
| `pattern general` | `%%MatrixMarket matrix coordinate pattern general` | Unweighted directed graph (most common) |
| `pattern symmetric` | `%%MatrixMarket matrix coordinate pattern symmetric` | Unweighted undirected graph (lower triangle only) |
| `real general` | `%%MatrixMarket matrix coordinate real general` | Weighted directed graph (floating-point weights) |
| `integer general` | `%%MatrixMarket matrix coordinate integer general` | Weighted directed graph (integer weights) |
| `integer symmetric` | `%%MatrixMarket matrix coordinate integer symmetric` | Weighted undirected graph (integer weights) |

{: .note }
For `symmetric` files, readers must generate both `(i, j)` and `(j, i)` for each stored entry where `i ≠ j`. Self-loops (`i = i`) are stored once and should not be duplicated.

**Reference**: [NIST Matrix Market Format Specification](https://math.nist.gov/MatrixMarket/formats.html)

---

## Tools

Tools for converting to and from MTX format:

| Tool | Description | Language |
|:-----|:------------|:---------|
| **`bvgraph_to_mtx`** | Convert BVGraph to MTX (multi-threaded) | C++ |
| **`WG2MTX`** | Convert BVGraph to MTX (WebGraph library) | Java |
| **`mtx-egr`** | Convert MTX to ECLgraph/EGR format (symmetrized) | C++ |

All tools are available at: [github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters)
