"""Gauge limits shared by schemas and calculations without an import cycle."""

MIN_GAUGE_STITCHES, MAX_GAUGE_STITCHES = 6.0, 40.0
MIN_GAUGE_ROWS, MAX_GAUGE_ROWS = 8.0, 50.0
INDEPENDENT_GAUGE_PARTS = frozenset({"帽子", "裙子"})
