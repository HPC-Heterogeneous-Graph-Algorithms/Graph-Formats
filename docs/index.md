---
layout: default
title: Home
nav_order: 1
permalink: /
---

# Graph Formats
{: .fs-9 .fw-700 }

Specifications for graph file formats used by [HPC-Heterogeneous-Graph-Algorithms](https://github.com/HPC-Heterogeneous-Graph-Algorithms).
{: .fs-5 .fw-300 }

[Graph Format Converters →](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters){: .btn .btn-primary .fs-5 .mb-4 .mb-md-0 .mr-2 }
[Graph Resources →](https://hpc-heterogeneous-graph-algorithms.github.io/Resources/){: .btn .btn-outline .fs-5 .mb-4 .mb-md-0 }

---

## Formats

| Format | Type | Node IDs | Weights | Extension | Details |
|:-------|:-----|:---------|:--------|:----------|:--------|
| **BVGraph** | Binary (compressed) | 0-indexed | No | `.graph` + `.properties` + `.offsets` | [Spec →]({{ site.baseurl }}/bvgraph) |
| **MTX** | Text (Matrix Market) | 1-indexed | Optional | `.mtx` | [Spec →]({{ site.baseurl }}/mtx) |
| **BGR** | Binary (CSR) | 0-indexed | Optional | `.bgr` | [Spec →]({{ site.baseurl }}/bgr) |
| **ECLgraph** | Binary (CSR) | 0-indexed | Optional | `.egr` | [Spec →]({{ site.baseurl }}/ecl) |
| **WGBin** | Binary (split files) | 0-indexed | No | `_offsets.bin` + `_edges.bin` | [Spec →]({{ site.baseurl }}/wgbin) |

---

## Overview

**BVGraph** is the compressed input format from the [LAW dataset collection](https://law.di.unimi.it/datasets.php) (WebGraph framework). It serves as the primary source format for large-scale web and social graphs. **MTX** (Matrix Market) and **BGR** (Binary CSR) are the two primary output formats produced by the [graph-format-converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters) tools, supporting both text-based and binary workflows. **ECLgraph** (`.egr`) is a CSR format developed at Texas State University, used in several GPU graph algorithm implementations. **WGBin** is a legacy intermediate format from an earlier conversion pipeline, storing offsets and edges in separate binary files.

---

## Related Projects

| Project | Description |
|:--------|:------------|
| [Graph Format Converters](https://github.com/HPC-Heterogeneous-Graph-Algorithms/graph-format-converters) | Convert BVGraph → MTX / BGR using multi-threaded C++ or Java |
| [Graph Resources](https://hpc-heterogeneous-graph-algorithms.github.io/Resources/) | Curated graph datasets, tools, and references |
| [SCC Analysis](https://github.com/LokeshVenkatachalam/Strongly-Connected-Components-Analysis) | Benchmark parallel SCC algorithms on large-scale graphs |
