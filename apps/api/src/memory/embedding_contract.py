"""Shared vector shape contract; storage additionally checks the loaded model."""
from __future__ import annotations

import math
from typing import Sequence

DEFAULT_EMBEDDING_DIMENSION = 384  # sentence-transformers/all-MiniLM-L6-v2
MAX_EMBEDDING_DIMENSION = 65536


def validate_vector(values: Sequence[float], dimension: int) -> list[float]:
    if not 0 < dimension <= MAX_EMBEDDING_DIMENSION or len(values) != dimension:
        raise ValueError(f"Embedding must have {dimension} dimensions")
    result = [float(value) for value in values]
    # Both Chroma and the SQLite BLOB contract store IEEE-754 float32.
    if not all(math.isfinite(value) and abs(value) <= 3.4028234663852886e38 for value in result):
        raise ValueError("Embedding must contain only finite float32-representable numbers")
    return result
