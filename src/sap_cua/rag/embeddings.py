from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class TextEmbeddingProvider(Protocol):
    version: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ImageEmbeddingProvider(Protocol):
    version: str
    dimensions: int

    def embed(self, paths: list[str]) -> list[list[float]]: ...


class HashEmbedding:
    """Explicit deterministic test embedding; not the production semantic default."""

    version = "test-hash-v1"
    dimensions = 384

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * self.dimensions
            for token in re.findall(r"\w+", text.lower()):
                index = (
                    int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
                    % self.dimensions
                )
                vector[index] += 1
            length = math.sqrt(sum(x * x for x in vector)) or 1
            vectors.append([x / length for x in vector])
        return vectors


class FastTextEmbedding:
    dimensions = 384
    version = "BAAI/bge-small-en-v1.5:fastembed-0.9:384"

    def __init__(self, cache_dir: str):
        from fastembed import TextEmbedding

        self.model = TextEmbedding("BAAI/bge-small-en-v1.5", cache_dir=cache_dir, threads=4)
        self.version += ":" + asset_fingerprint(self.model)

    def embed(self, texts):
        return [vector.tolist() for vector in self.model.embed(texts)]


class FastImageEmbedding:
    dimensions = 512
    version = "Qdrant/clip-ViT-B-32-vision:fastembed-0.9:512"

    def __init__(self, cache_dir: str):
        from fastembed import ImageEmbedding

        self.model = ImageEmbedding("Qdrant/clip-ViT-B-32-vision", cache_dir=cache_dir, threads=4)
        self.version += ":" + asset_fingerprint(self.model)

    def embed(self, paths):
        return [vector.tolist() for vector in self.model.embed(paths)]


class Reranker(Protocol):
    version: str

    def score(self, query: str, passages: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    version = "Xenova/ms-marco-MiniLM-L-6-v2:fastembed-0.9"

    def __init__(self, cache_dir: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.model = TextCrossEncoder(
            "Xenova/ms-marco-MiniLM-L-6-v2", cache_dir=cache_dir, threads=4
        )
        self.version += ":" + asset_fingerprint(self.model)

    def score(self, query, passages):
        return [float(x) for x in self.model.rerank(query, passages)]


class TokenOverlapReranker:
    version = "test-token-overlap-v1"

    def score(self, query, passages):
        q = set(re.findall(r"\w+", query.lower()))
        return [len(q & set(re.findall(r"\w+", p.lower()))) / max(len(q), 1) for p in passages]


def asset_fingerprint(model):
    """Hash actual ONNX/tokenizer assets so changed weights force a new index."""
    from pathlib import Path

    current = model
    for _ in range(4):
        directory = getattr(current, "_model_dir", None)
        if directory is not None:
            digest = hashlib.sha256()
            files = sorted(
                path
                for path in Path(directory).rglob("*")
                if path.is_file() and not path.name.startswith(".")
            )
            for path in files:
                digest.update(str(path.relative_to(directory)).encode())
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            if not files:
                raise RuntimeError("Embedding model assets missing")
            return digest.hexdigest()[:20]
        current = getattr(current, "model", None)
    raise RuntimeError("Cannot identify embedding model assets")
