import math


def retrieval_metrics(ranked_ids, relevant_ids, k=5):
    relevant = set(relevant_ids)
    seen = set()
    ranked = []
    for id in ranked_ids:
        if id not in seen:
            ranked.append(id)
            seen.add(id)
    ranked = ranked[:k]
    recall = len(set(ranked) & relevant) / max(len(relevant), 1)
    reciprocal = next((1 / (i + 1) for i, id in enumerate(ranked) if id in relevant), 0)
    dcg = sum(1 / math.log2(i + 2) for i, id in enumerate(ranked) if id in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return {"recall_at_k": recall, "mrr": reciprocal, "ndcg": dcg / ideal if ideal else 0}


RETRIEVAL_CASES = [
    ("OData receiver fails with HTTP 401 OAuth credentials", ["error-401", "oauth-alias"]),
    ("JMS queue retry asynchronous duplicate message handling", ["adapter-jms"]),
    (
        "No ProcessDirect consumer DirectVmConsumerNotAvailableException",
        ["error-directvmconsumernotavailableexception", "component-processdirect"],
    ),
    ("Receiver 429 Retry-After rate limit", ["error-429"]),
    ("SFTP host key directory polling security", ["adapter-sftp"]),
    (
        "Verify a deployed flow processed a fresh test message using MPL correlation",
        ["mpl-correlation"],
    ),
    ("Insert a router with default route conditions", ["component-router"]),
    (
        "XML namespaces JSON mapping transformation fixture",
        ["xml-mapping", "error-mapping_failure"],
    ),
]
