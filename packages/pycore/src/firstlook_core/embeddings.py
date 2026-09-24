"""Deterministic local embeddings.

Character n-gram feature hashing into a fixed 1024-dim unit vector. Not a
semantic model: it captures surface similarity (names, spellings, emails),
which is what entity resolution needs, and it runs offline with no API key.
Real embedding models are routed through the gateway when configured.
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata

DIM = 1024


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def hash_embed(text: str, dim: int = DIM) -> list[float]:
    text = f" {_normalise(text)} "
    vec = [0.0] * dim
    for n in (2, 3, 4):
        for i in range(len(text) - n + 1):
            h = int.from_bytes(hashlib.blake2b(text[i : i + n].encode(), digest_size=8).digest(), "big")
            vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
