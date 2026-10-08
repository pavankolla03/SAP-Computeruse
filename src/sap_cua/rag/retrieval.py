from __future__ import annotations

from sap_cua.rag.schemas import Scope


def route_collections(query: str) -> list[str]:
    q = query.lower()
    domains = {
        "cloud_integration",
        "architecture_patterns",
        "customer_standards",
        "successful_solutions",
        "trajectories",
    }
    groups = {
        "adapters": ("odata", "https", "http", "sftp", "soap", "jms", "adapter"),
        "components": (
            "router",
            "modifier",
            "splitter",
            "gather",
            "multicast",
            "groovy",
            "component",
            "step",
        ),
        "security": ("oauth", "credential", "401", "403", "security", "certificate"),
        "mpl_errors": ("error", "fail", "401", "403", "429", "500", "timeout", "exception"),
        "known_failures": ("error", "fail", "repair", "fix", "timeout"),
        "monitoring": ("mpl", "monitor", "log", "trace", "status"),
        "mapping": ("map", "transform", "json", "xml"),
        "apim": ("proxy", "api management"),
        "event_mesh": ("event mesh", "event-driven"),
    }
    for domain, words in groups.items():
        if any(word in q for word in words):
            domains.add(domain)
    return sorted(domains)


class Retriever:
    def __init__(self, store, embeddings, reranker, *, include_trajectories=True):
        self.store, self.embeddings, self.reranker = store, embeddings, reranker
        self.include_trajectories = include_trajectories

    def search(
        self, query: str, scope: Scope, *, limit: int = 6, max_chars: int = 7000, collections=None
    ):
        if not query.strip() or len(query) > 4000 or not 1 <= limit <= 10:
            raise ValueError("Invalid retrieval query or limit")
        collections = list(collections or route_collections(query))
        if not self.include_trajectories:
            collections = [c for c in collections if c != "trajectories"]
        from sap_cua.engineering.telemetry import retrievals, tracer

        with tracer.start_as_current_span("sap.rag.embedding") as span:
            span.set_attribute("embedding.version", self.embeddings.version)
            vector = self.embeddings.embed([query])[0]
        retrievals.add(1, {"stage": "embedding"})
        hits = self.store.search(
            query, vector, scope, collections, self.embeddings.version, limit=30
        )
        if not hits:
            return []
        with tracer.start_as_current_span("sap.rag.rerank") as span:
            span.set_attribute("rag.candidates", len(hits))
            scores = self.reranker.score(query, [h.title + "\n" + h.content for h in hits])
        retrievals.add(1, {"stage": "reranking"})
        for hit, score in zip(hits, scores, strict=True):
            hit.rerank_score = score
        hits.sort(key=lambda h: (h.rerank_score, h.score), reverse=True)
        result = []
        remaining = max_chars
        for hit in hits:
            if len(result) >= limit or remaining < 100:
                break
            # Do not admit completely unrelated vector neighbors without lexical or semantic evidence.
            if hit.lexical_score <= 0 and hit.vector_score < 0.55:
                continue
            hit.content = hit.content[:remaining]
            remaining -= len(hit.content)
            result.append(hit)
        return result
