from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DOMAINS = {
    "sap_docs",
    "integration_suite",
    "cloud_integration",
    "adapters",
    "components",
    "mapping",
    "groovy",
    "xslt",
    "security",
    "monitoring",
    "mpl_errors",
    "apim",
    "event_mesh",
    "architecture_patterns",
    "customer_standards",
    "known_failures",
    "successful_solutions",
    "trajectories",
    "screenshots",
}


class Scope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    customer: str = Field(min_length=1, max_length=100, pattern=r"^[\w][\w.-]*$")
    tenant: str = Field(min_length=1, max_length=100, pattern=r"^[\w][\w.-]*$")
    role: Literal["viewer", "engineer", "admin"] = "engineer"


class KnowledgeObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=200)
    document_type: Literal[
        "text",
        "pattern",
        "error_playbook",
        "code_pattern",
        "iflow_template",
        "trajectory",
        "screenshot_state",
        "tenant_knowledge",
    ]
    collection: str
    sap_product: str = "Integration Suite"
    sap_module: str = "Cloud Integration"
    topic: str
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=1000000)
    source: str
    source_version: str = "1"
    source_date: str | None = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    tenant_scope: str = "global"
    customer_scope: str = "global"
    security_classification: Literal["public", "internal", "restricted"] = "public"
    tags: list[str] = Field(default_factory=list, max_length=50)
    applicable_actions: list[str] = Field(default_factory=list, max_length=100)
    applicable_errors: list[str] = Field(default_factory=list, max_length=50)
    artifact_types: list[str] = Field(default_factory=list, max_length=50)
    embedding_version: str = ""
    hash: str = ""
    facts: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False
    license: str = "internal-original"
    provenance_kind: Literal["original", "external", "verified_execution"] = "original"

    @model_validator(mode="after")
    def validate_scope(self):
        if self.collection not in DOMAINS:
            raise ValueError("Unknown knowledge collection")
        if self.customer_scope == "global" and self.tenant_scope != "global":
            raise ValueError("Global customer cannot contain private tenant knowledge")
        if self.customer_scope == "global" and self.security_classification != "public":
            raise ValueError("Global knowledge must be public")
        self.hash = hashlib.sha256(self.content.encode()).hexdigest()
        return self


class SearchHit(BaseModel):
    facts: dict[str, Any] = Field(default_factory=dict)
    customer_scope: str = "global"
    tenant_scope: str = "global"
    id: str
    chunk_id: str
    title: str
    content: str
    collection: str
    source: str
    source_version: str
    hash: str
    embedding_version: str
    score: float
    vector_score: float = 0
    lexical_score: float = 0
    rerank_score: float | None = None
