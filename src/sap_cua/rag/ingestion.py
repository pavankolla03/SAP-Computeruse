from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sap_cua.rag.schemas import KnowledgeObject, Scope
from sap_cua.security import sanitize_data


def chunk_text(text: str, size: int = 1400, overlap: int = 180):
    if size <= overlap or overlap < 0:
        raise ValueError("Invalid chunk parameters")
    # Character bound keeps BGE's 512-token window useful for typical English SAP text.
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary
        content = text[start:end].strip()
        if content:
            yield content
        if end == len(text):
            break
        start = end - overlap


class Ingestor:
    def __init__(self, store, embeddings):
        self.store, self.embeddings = store, embeddings

    def ingest(self, document: KnowledgeObject, scope: Scope):
        if scope.role == "viewer":
            raise PermissionError("Viewer cannot ingest knowledge")
        if scope.role != "admin" and (
            document.customer_scope == "global"
            or document.customer_scope != scope.customer
            or document.tenant_scope != scope.tenant
        ):
            raise PermissionError("Document scope is not authorized")
        if not document.approved:
            raise ValueError("Only approved sources may be indexed")
        safe = sanitize_data(document.model_dump())
        document = KnowledgeObject.model_validate(safe)
        document.embedding_version = self.embeddings.version
        chunks = list(chunk_text(document.title + "\n" + document.content))
        identity = hashlib.sha256(
            json.dumps(
                {k: v for k, v in document.model_dump().items() if k != "retrieved_at"},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if self.store.has_version(document, identity):
            return {"changed": False, "chunks": 0, "id": document.id}
        vectors = self.embeddings.embed(chunks)
        self.store.put(document, identity, chunks, vectors)
        return {"changed": True, "chunks": len(chunks), "id": document.id, "hash": document.hash}

    def ingest_jsonl(self, path: Path, scope: Scope):
        return [
            self.ingest(KnowledgeObject.model_validate_json(line), scope)
            for line in path.read_text().splitlines()
            if line.strip()
        ]
