---
layout: default
title: BVGraph
nav_order: 2
permalink: /bvgraph/
---

# BVGraph Format
{: .fs-8 }

Compressed graph format from the WebGraph framework
{: .fs-5 .fw-300 }

---

## Overview

BVGraph is a highly compressed graph representation developed by **Paolo Boldi and Sebastiano Vigna** and first described in their WWW 2004 paper, *"The WebGraph Framework I: Compression Techniques."* It is the native storage format of the [WebGraph framework](https://webgraph.di.unimi.it/) and is used extensively by the [LAW (Laboratory for Web Algorithmics) dataset collection](http://law.di.unimi.it/datasets.php) at the University of Milan.

BVGraph achieves very high compression ratios on web graphs and social networks—often representing each link in **fewer than 3 bits**—by exploiting two key properties of these graphs:

- **Locality**: successor lists of nearby nodes tend to be similar, so a node can *reference* a nearby node's list and encode only the differences.
- **Consecutivity**: successor lists often contain long contiguous runs of IDs, which compress well as *(start, length)* intervals.

On top of these structural techniques, BVGraph encodes all integers using variable-length codes (gamma, delta, and zeta codes) that assign shorter representations to smaller values.

---

## File Components

Each BVGraph dataset consists of three files sharing a common basename:

| File | Description |
|------|-------------|
| `<name>.graph` | Compressed bitstream containing all successor lists, packed at the bit level. This is the main data file. |
| `<name>.properties` | Java properties file with graph metadata: node/arc counts and all compression parameters needed to decode the `.graph` file. |
| `<name>.offsets` | Bit-level offsets for each node's entry in the `.graph` file. Stores the delta-coded bit position of each node, enabling random access and parallel decompression. |

The `.offsets` file can be regenerated from the `.graph` and `.properties` files:

```bash
# C++ (no Java required)
./bvgraph_gen_offsets data/eu-2005

# Java (using the WebGraph library)
java -cp jlibs/*: it.unimi.dsi.webgraph.BVGraph data/eu-2005 -O
```

---

## Properties File

The `.properties` file is a plain-text Java properties file that stores all metadata and compression parameters required to decode the `.graph` bitstream.

### Example

```properties
#BVGraph
#Thu Jan 01 00:00:00 CET 2024
graphclass=it.unimi.dsi.webgraph.BVGraph
version=0
nodes=862664
arcs=19235140
windowsize=7
maxrefcount=3
minintervallength=4
zetak=3
compressionflags=
```

### Key Definitions

| Key | Type | Description |
|-----|------|-------------|
| `nodes` | integer | Total number of vertices in the graph. |
| `arcs` | integer | Total number of directed edges (arcs). |
| `windowsize` | integer | Size of the reference window. A node can reference any of the previous *windowsize* nodes. Typical value: **7**. |
| `maxrefcount` | integer | Maximum reference chain length. If node A references B which references C, the chain length is 2. Limits recursive lookups during decoding. Typical value: **3**. |
| `minintervallength` | integer | Minimum run length for interval encoding. Contiguous runs of successor IDs shorter than this threshold are not encoded as intervals. Set to **0** to disable interval encoding entirely. Typical value: **4**. |
| `zetak` | integer | The *k* parameter for zeta coding (ζ_k). Controls the "shrinking factor" that tunes the code for power-law distributions. Typical value: **3**. |
| `compressionflags` | string | Pipe-delimited list of coding overrides for each component (e.g., `RESIDUALS_ZETA \| OUTDEGREES_GAMMA`). When empty, default codings apply. |

### Default Coding Assignments

When `compressionflags` is empty, the following defaults are used:

| Component | Default Coding |
|-----------|---------------|
| Outdegrees | Gamma (γ) |
| Blocks | Gamma (γ) |
| Block counts | Gamma (γ) |
| Residuals | Zeta (ζ_k) |
| References | Unary |
| Offsets | Gamma (γ) |

The `compressionflags` string can override any of these using the syntax `COMPONENT_CODING`, separated by `|`. For example: `RESIDUALS_ZETA | BLOCKS_DELTA | OUTDEGREES_DELTA`.

---

## Integer Coding Schemes

BVGraph uses several variable-length integer codes to represent non-negative integers compactly. Smaller values receive shorter bit representations. All codes are read **MSB-first** (most significant bit first) from the bitstream.

### Unary Code

Encodes value *x* as *x* zero bits followed by a single 1 bit.

| Value | Encoding |
|-------|----------|
| 0 | `1` |
| 1 | `01` |
| 2 | `001` |
| 3 | `0001` |
| *x* | *x* zeros + `1` |

**Cost**: *x + 1* bits. Optimal for geometric distributions. Used primarily for reference values.

### Gamma Code (γ) — Elias Gamma

Encodes *x + 1* by writing the bit length of *x + 1* in unary, followed by the value of *x + 1* without its leading 1-bit.

1. Compute *ℓ = ⌊log₂(x + 1)⌋*
2. Write *ℓ* in unary (*ℓ* zeros + one 1-bit)
3. Write the lower *ℓ* bits of *x + 1*

| Value | ℓ | Encoding |
|-------|---|----------|
| 0 | 0 | `1` |
| 1 | 1 | `01 0` |
| 2 | 1 | `01 1` |
| 3 | 2 | `001 00` |
| 6 | 2 | `001 11` |
| 7 | 3 | `0001 000` |

**Cost**: *2⌊log₂(x + 1)⌋ + 1* bits. Default coding for outdegrees, blocks, and block counts.

### Delta Code (δ) — Elias Delta

Like gamma, but the length prefix itself is gamma-coded rather than unary-coded. This is more efficient for large values.

1. Compute *ℓ = ⌊log₂(x + 1)⌋*
2. Write *ℓ* using **gamma** coding
3. Write the lower *ℓ* bits of *x + 1*

**Cost**: *⌊log₂(ℓ)⌋ + 2⌊log₂(ℓ + 1)⌋ + 1* bits. More efficient than gamma for values larger than ~32.

### Zeta Code (ζ_k) — Parameterized Code

A family of codes parameterized by a positive integer *k* (the "shrinking factor"), designed by Boldi and Vigna specifically for power-law distributed gap values in web graphs. The parameter *k* controls how the code trades off between small and large values.

**Encoding of value *x* with parameter *k*:**

1. Compute *h = ⌊log₂(x + 1) / k⌋* (the "quotient")
2. Write *h* in unary
3. Compute *m = x + 1 − 2^(hk)* (the "remainder")
4. If *m < 2^(hk)*, write *m* in *hk + k − 1* bits
5. Otherwise, write *2m* or *2m + 1* in *hk + k* bits

With *k = 3* (the typical value, called ζ₃), this is optimized for the power-law distributions commonly found in web graph successor gaps. Default coding for residual values.

### Nibble Code

A variable-length code using 4-bit chunks. Each chunk consists of:
- 1 **continuation bit** (1 = more chunks follow, 0 = last chunk)
- 3 **data bits**

Chunks are read in sequence. The 3-bit values from each chunk are concatenated (least-significant first) to form the final value.

| Value | Encoding |
|-------|----------|
| 0 | `0 000` |
| 7 | `0 111` |
| 8 | `1 000 · 0 001` |

---

## Successor List Encoding

Each node's successor list is encoded as a sequence of fields in the `.graph` bitstream. The fields appear in the following order:

### 1. Outdegree

The number of successors (outgoing edges) for this node, encoded using the configured outdegree coding (default: gamma).

```
outdegree = readGamma(bitstream)
```

If the outdegree is 0, no further fields are read for this node.

### 2. Reference

If `windowsize > 0`, the next field is a reference offset *r* encoded using the configured reference coding (default: unary). This indicates that the successor list of node *(x − r)* should be used as a template.

- *r = 0*: no reference; the successor list is encoded independently.
- *r > 0*: reference node *(x − r)*; copy blocks and differences follow.

```
ref = readUnary(bitstream)   // 0 means no reference
```

### 3. Copy Blocks

When *r > 0*, a **block count** is read (gamma-coded), followed by a sequence of block lengths. These blocks describe which elements from the referenced node's successor list to **copy** and which to **skip**, in alternating fashion:

- Block 0: number of elements to **copy** from the start of the referenced list
- Block 1: number of elements to **skip**
- Block 2: number of elements to **copy**
- Block 3: number of elements to **skip**
- ...and so on, alternating copy/skip

```
blockCount = readGamma(bitstream)
blocks[0] = readGamma(bitstream)         // first block: raw value
blocks[i] = readGamma(bitstream) + 1     // subsequent blocks: +1 offset
```

If the block count is **even**, all remaining elements from the referenced list (past the last explicit block) are implicitly **copied**. If odd, remaining elements are implicitly **skipped**.

### 4. Intervals

If `minintervallength > 0` and there are extra successors (beyond those copied from the reference), the decoder reads an **interval count** (always gamma-coded):

- **Interval count** = 0: no intervals present.
- **Interval count** > 0: that many *(left, length)* pairs follow.

For the first interval:
- *left₀* is encoded as a signed offset from *x* using zigzag encoding: `left₀ = nat2int(readGamma()) + x`
- *length₀* = `readGamma() + minintervallength`

For subsequent intervals (*i ≥ 1*):
- *leftᵢ* = `readGamma() + prev_end + 1` (gap from the end of the previous interval)
- *lengthᵢ* = `readGamma() + minintervallength`

Each interval represents the contiguous range of successor IDs: `[left, left + length)`.

### 5. Residuals

Any remaining successors that are neither copied from the reference nor covered by intervals are encoded as **residuals** using gap coding:

- *residual₀*: signed offset from *x* using zigzag encoding: `residual₀ = x + nat2int(readZeta(k))`
- *residualᵢ* (for *i ≥ 1*): `residualᵢ₋₁ + readZeta(k) + 1` (strictly increasing gaps)

Residuals are encoded using the configured residual coding (default: zeta with parameter *k*).

### 6. Three-Way Merge

The final successor list for node *x* is the **sorted merge** of three sources:

1. **Block-copied elements** from the referenced node's list
2. **Interval elements** expanded from the *(left, length)* pairs
3. **Residual elements** decoded from gap-coded values

By construction, each source produces values in sorted order, so a standard three-way merge yields the complete sorted successor list.

---

## Signed Integer Encoding (nat2int)

Some values (interval start offsets and first residuals) are encoded as signed differences from the current node ID. BVGraph uses **zigzag encoding** to map signed integers to non-negative integers:

| Natural | Integer |
|---------|---------|
| 0 | 0 |
| 1 | −1 |
| 2 | 1 |
| 3 | −2 |
| 4 | 2 |

The decoding formula is: `nat2int(x) = (x >> 1) ^ -(x & 1)`

This allows both positive and negative differences to be encoded efficiently using codes designed for non-negative integers.

---

## Parallel Decompression

The `.offsets` file stores the bit position of each node's entry in the `.graph` file as delta-coded values. Once loaded, these offsets enable random access to any node and multi-threaded parallel decoding.

### How It Works

1. **Load offsets**: Read the `.offsets` file to build an array mapping each node ID to its bit position in the `.graph` file.
2. **Partition nodes**: Divide the node range `[0, N)` into chunks, one per thread.
3. **Warm up reference windows**: Each thread must decode `windowSize` nodes *before* its assigned chunk start. This "warm-up" phase populates the thread's local reference window so that references within the chunk can be correctly resolved.
4. **Decode independently**: Each thread decodes its chunk using its own `InputBitStream` and cyclic reference window, writing results into pre-allocated output arrays at computed offsets.

### Reference Window

The decoder maintains a **cyclic buffer** of size `windowSize + 1` that stores the most recently decoded successor lists. When a node references node *(x − r)*, the decoder looks up that node's successor list in the cyclic buffer. This means:

- Sequential decoding naturally maintains the window.
- For parallel decoding, each thread must warm up its window before decoding its first assigned node.
- The warm-up cost is at most `windowSize` extra node decodings per thread (typically 7 nodes).

---

## Example Datasets

The [LAW dataset collection](http://law.di.unimi.it/datasets.php) hosts hundreds of web graphs and social networks in BVGraph format. Here are some commonly used datasets:

| Dataset | Nodes | Edges | Compressed Size |
|---------|------:|------:|----------------:|
| [cnr-2000](http://law.di.unimi.it/webdata/cnr-2000/) | 325K | 3.2M | ~1 MB |
| [eu-2005](http://law.di.unimi.it/webdata/eu-2005/) | 862K | 19M | ~9 MB |
| [in-2004](http://law.di.unimi.it/webdata/in-2004/) | 1.4M | 17M | ~8 MB |
| [indochina-2004](http://law.di.unimi.it/webdata/indochina-2004/) | 7.4M | 194M | ~34 MB |
| [uk-2014](http://law.di.unimi.it/webdata/uk-2014/) | 788M | 47B | ~26 GB |

### Downloading

Datasets follow a consistent URL pattern:

```bash
BASE_URL="http://data.law.di.unimi.it/webdata"
GRAPH="eu-2005"

# Download the required files
wget "$BASE_URL/$GRAPH/$GRAPH.graph"
wget "$BASE_URL/$GRAPH/$GRAPH.properties"

# The .offsets file can be downloaded if available, or generated:
./bvgraph_gen_offsets $GRAPH
```

---

## References

- P. Boldi, S. Vigna. *"The WebGraph Framework I: Compression Techniques."* WWW 2004. [Paper](http://vigna.di.unimi.it/papers.php#BoVWFI)
- [WebGraph Java library](https://github.com/vigna/webgraph) — the reference implementation
- [DSI Utilities](https://github.com/vigna/dsiutils) — `InputBitStream` and integer coding implementations
- [LAW dataset collection](http://law.di.unimi.it/datasets.php) — hundreds of BVGraph datasets
- [C++ BVGraph decoder](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters) — pure C++ implementation with parallel decompression
