"""PostgreSQL full-text + pgvector storage with mandatory tenant filters."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter

from sap_cua.rag.schemas import SearchHit


def key(document):
    return hashlib.sha256(
        f"{document.customer_scope}\0{document.tenant_scope}\0{document.id}".encode()
    ).hexdigest()


def visible(document, scope):
    allowed = (document.customer_scope == "global" and document.tenant_scope == "global") or (
        document.customer_scope == scope.customer
        and document.tenant_scope in ("global", scope.tenant)
    )
    return allowed and (document.security_classification != "restricted" or scope.role == "admin")


class MemoryKnowledgeStore:
    """Explicit in-memory test implementation; never a silent database fallback."""

    def __init__(self):
        self.versions = {}
        self.active = {}

    def has_version(self, document, identity):
        return self.active.get((key(document), document.embedding_version)) == identity

    def put(self, document, identity, chunks, vectors):
        self.versions[(key(document), identity)] = (document, chunks, vectors)
        self.active[(key(document), document.embedding_version)] = identity

    def search(self, query, vector, scope, collections, embedding_version, limit=30):
        rows = []
        terms = re.findall(r"\w+", query.lower())
        for (doc_key, version), identity in self.active.items():
            document, chunks, vectors = self.versions[(doc_key, identity)]
            if (
                version != embedding_version
                or document.collection not in collections
                or not visible(document, scope)
            ):
                continue
            for index, (chunk, v) in enumerate(zip(chunks, vectors, strict=True)):
                counts = Counter(re.findall(r"\w+", chunk.lower()))
                lexical = sum(counts[t] / (counts[t] + 1.2) for t in terms)
                cosine = sum(a * b for a, b in zip(vector, v, strict=True))
                rows.append(
                    SearchHit(
                        facts=document.facts,
                        customer_scope=document.customer_scope,
                        tenant_scope=document.tenant_scope,
                        id=document.id,
                        chunk_id=f"{doc_key}:{identity}:{index}",
                        title=document.title,
                        content=chunk,
                        collection=document.collection,
                        source=document.source,
                        source_version=document.source_version,
                        hash=document.hash,
                        embedding_version=version,
                        score=lexical + cosine,
                        lexical_score=lexical,
                        vector_score=cosine,
                    )
                )
        return sorted(rows, key=lambda row: row.score, reverse=True)[:limit]


DDL = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS knowledge_versions (
  document_key text NOT NULL, version_id text NOT NULL, id text NOT NULL,
  customer_scope text NOT NULL, tenant_scope text NOT NULL,
  classification text NOT NULL, collection text NOT NULL,
  embedding_version text NOT NULL, active boolean NOT NULL DEFAULT true,
  document jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(document_key,version_id)
);
CREATE TABLE IF NOT EXISTS knowledge_chunks (
  chunk_id text PRIMARY KEY, document_key text NOT NULL, version_id text NOT NULL,
  content text NOT NULL, embedding vector(384) NOT NULL,
  search tsvector GENERATED ALWAYS AS (to_tsvector('english',content)) STORED,
  FOREIGN KEY(document_key,version_id) REFERENCES knowledge_versions(document_key,version_id)
);
CREATE INDEX IF NOT EXISTS knowledge_scope ON knowledge_versions(customer_scope,tenant_scope,collection,embedding_version) WHERE active;
CREATE INDEX IF NOT EXISTS knowledge_lexical ON knowledge_chunks USING gin(search);
CREATE INDEX IF NOT EXISTS knowledge_dense ON knowledge_chunks USING hnsw(embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS screenshot_memory (
 id text PRIMARY KEY, customer_scope text NOT NULL, tenant_scope text NOT NULL,
 page text NOT NULL, module text NOT NULL, embedding_version text NOT NULL,
 embedding vector(512) NOT NULL, metadata jsonb NOT NULL
);
"""


class PostgresKnowledgeStore:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("SAP_CUA_DATABASE_URL is required for RAG")
        self.dsn = dsn

    def connect(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.dsn, connect_timeout=5, row_factory=dict_row)

    def migrate(self):
        with self.connect() as db:
            db.execute(DDL)

    def has_version(self, document, identity):
        with self.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM knowledge_versions WHERE document_key=%s AND version_id=%s AND active",
                    (key(document), identity),
                ).fetchone()
                is not None
            )

    def put(self, document, identity, chunks, vectors):
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/embedding count mismatch")
        if any(len(v) != 384 or not all(math.isfinite(x) for x in v) for v in vectors):
            raise ValueError("Invalid embedding")
        doc_key = key(document)
        with self.connect() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (doc_key,))
            db.execute(
                "UPDATE knowledge_versions SET active=false WHERE document_key=%s AND embedding_version=%s",
                (doc_key, document.embedding_version),
            )
            db.execute(
                """INSERT INTO knowledge_versions(document_key,version_id,id,customer_scope,tenant_scope,classification,collection,embedding_version,document)
                          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                          ON CONFLICT(document_key,version_id) DO UPDATE SET active=true""",
                (
                    doc_key,
                    identity,
                    document.id,
                    document.customer_scope,
                    document.tenant_scope,
                    document.security_classification,
                    document.collection,
                    document.embedding_version,
                    document.model_dump_json(),
                ),
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.execute(
                    "INSERT INTO knowledge_chunks VALUES(%s,%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING",
                    (f"{doc_key}:{identity}:{index}", doc_key, identity, chunk, json.dumps(vector)),
                )

    def search(self, query, vector, scope, collections, embedding_version, limit=30):
        if len(vector) != 384 or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid query embedding")
        # Tenant/classification/version filters apply BEFORE either candidate ranking.
        sql = """WITH scoped AS MATERIALIZED (
          SELECT c.chunk_id,c.content,c.embedding,c.search,d.document,d.id,d.collection
          FROM knowledge_chunks c JOIN knowledge_versions d USING(document_key,version_id)
          WHERE d.active AND d.embedding_version=%s AND d.collection=ANY(%s)
          AND ((d.customer_scope='global' AND d.tenant_scope='global') OR (d.customer_scope=%s AND d.tenant_scope IN ('global',%s)))
          AND (d.classification<>'restricted' OR %s='admin')
        ), dense AS (
          SELECT chunk_id,1-(embedding <=> %s::vector) AS similarity,
                 row_number() OVER(ORDER BY embedding <=> %s::vector) AS rank
          FROM scoped ORDER BY embedding <=> %s::vector LIMIT 30
        ), lexical AS (
          SELECT chunk_id,ts_rank_cd(search,websearch_to_tsquery('english',%s)) AS similarity,
                 row_number() OVER(ORDER BY ts_rank_cd(search,websearch_to_tsquery('english',%s)) DESC) AS rank
          FROM scoped WHERE search @@ websearch_to_tsquery('english',%s)
          ORDER BY similarity DESC LIMIT 30
        ), scores AS (
          SELECT COALESCE(d.chunk_id,l.chunk_id) AS chunk_id,
                 COALESCE(1.0/(60+d.rank),0)+COALESCE(1.0/(60+l.rank),0) AS score,
                 COALESCE(d.similarity,0) AS vector_score, COALESCE(l.similarity,0) AS lexical_score
          FROM dense d FULL JOIN lexical l USING(chunk_id)
        ) SELECT s.*,scores.score,scores.vector_score,scores.lexical_score
          FROM scoped s JOIN scores USING(chunk_id) ORDER BY scores.score DESC LIMIT %s"""
        v = json.dumps(vector)
        with self.connect() as db:
            rows = db.execute(
                sql,
                (
                    embedding_version,
                    collections,
                    scope.customer,
                    scope.tenant,
                    scope.role,
                    v,
                    v,
                    v,
                    query,
                    query,
                    query,
                    limit,
                ),
            ).fetchall()
        hits = []
        for row in rows:
            doc = row["document"]
            hits.append(
                SearchHit(
                    facts=doc.get("facts", {}),
                    customer_scope=doc["customer_scope"],
                    tenant_scope=doc["tenant_scope"],
                    id=row["id"],
                    chunk_id=row["chunk_id"],
                    title=doc["title"],
                    content=row["content"],
                    collection=row["collection"],
                    source=doc["source"],
                    source_version=doc["source_version"],
                    hash=doc["hash"],
                    embedding_version=embedding_version,
                    score=float(row["score"]),
                    vector_score=float(row["vector_score"]),
                    lexical_score=float(row["lexical_score"]),
                )
            )
        return hits

    def counts(self, scope):
        with self.connect() as db:
            rows = db.execute(
                """SELECT collection,count(*) AS count FROM knowledge_versions WHERE active
                AND ((customer_scope='global' AND tenant_scope='global') OR (customer_scope=%s AND tenant_scope IN ('global',%s)))
                AND (classification<>'restricted' OR %s='admin') GROUP BY collection""",
                (scope.customer, scope.tenant, scope.role),
            ).fetchall()
        return {r["collection"]: r["count"] for r in rows}

    def put_screenshot(self, id, scope, page, module, version, vector, metadata):
        if len(vector) != 512 or not all(math.isfinite(x) for x in vector):
            raise ValueError("Invalid image embedding")
        from sap_cua.security import sanitize_data

        metadata = sanitize_data(metadata)
        scoped_id = hashlib.sha256(f"{scope.customer}:{scope.tenant}:{id}".encode()).hexdigest()
        with self.connect() as db:
            db.execute(
                """INSERT INTO screenshot_memory VALUES(%s,%s,%s,%s,%s,%s,%s::vector,%s::jsonb)
                        ON CONFLICT(id) DO UPDATE SET embedding=excluded.embedding,metadata=excluded.metadata,embedding_version=excluded.embedding_version""",
                (
                    scoped_id,
                    scope.customer,
                    scope.tenant,
                    page,
                    module,
                    version,
                    json.dumps(vector),
                    json.dumps(metadata),
                ),
            )

    def search_screenshots(self, scope, page, module, version, vector, limit=5):
        if len(vector) != 512 or not all(math.isfinite(x) for x in vector) or not 1 <= limit <= 10:
            raise ValueError("Invalid image query")
        with self.connect() as db:
            return db.execute(
                """SELECT id,metadata,1-(embedding <=> %s::vector) AS score FROM screenshot_memory
              WHERE customer_scope=%s AND tenant_scope=%s AND page=%s AND module=%s AND embedding_version=%s
              ORDER BY embedding <=> %s::vector LIMIT %s""",
                (
                    json.dumps(vector),
                    scope.customer,
                    scope.tenant,
                    page,
                    module,
                    version,
                    json.dumps(vector),
                    limit,
                ),
            ).fetchall()
