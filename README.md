# Graph-Formats

Specifications for graph formats used by
[HPC-Heterogeneous-Graph-Algorithms](https://github.com/HPC-Heterogeneous-Graph-Algorithms).

Documentation: <https://hpc-heterogeneous-graph-algorithms.github.io/Graph-Formats/>

## Check BGR v2 files

The repository includes a Python 3 checker with no third-party dependencies:

```bash
# Validate flags, counts, widths, and exact file size.
python3 tools/check_bgr.py graph.bgr

# Also stream-validate every cumulative row end and destination.
python3 tools/check_bgr.py --full graph.bgr

# Recursively validate all .bgr files in a directory.
python3 tools/check_bgr.py /path/to/graphs
```

Run its tests with:

```bash
python3 -m unittest discover -s tests -v
```