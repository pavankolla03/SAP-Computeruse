"""Bounded approved-source ingestion. Source text remains data, never instructions.

An administrator supplies provenance and reuse permission with each source.
URL fetching accepts only explicitly allowlisted HTTPS origins, disallows private
addresses and redirects, and uses no ambient proxy or credential settings.
"""

import ipaddress
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from sap_cua.rag.schemas import KnowledgeObject


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div", "li", "h1", "h2", "h3", "br"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def source_document(data: bytes, metadata: dict, *, content_type: str):
    if len(data) > 2_000_000:
        raise ValueError("Source exceeds 2 MB bound")
    if not metadata.get("approved") or not metadata.get("license"):
        raise ValueError("Source approval and reuse permission are required")
    text = data.decode("utf-8", errors="strict")
    if content_type == "text/html":
        parser = TextExtractor()
        parser.feed(text)
        text = " ".join(parser.parts)
    elif content_type not in ("text/plain", "text/markdown"):
        raise ValueError("Unsupported source format")
    return KnowledgeObject.model_validate({**metadata, "content": text})


def ingest_file(path, metadata, ingestor, scope):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Source exceeds 2 MB bound")
    content_type = {".html": "text/html", ".md": "text/markdown", ".txt": "text/plain"}.get(
        path.suffix
    )
    return ingestor.ingest(
        source_document(path.read_bytes(), metadata, content_type=content_type), scope
    )


def ingest_url(url, metadata, ingestor, scope, *, allowed_origins):
    if scope.role != "admin":
        raise PermissionError("External source ingestion requires administrator scope")
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or parts.fragment
        or origin not in allowed_origins
    ):
        raise ValueError("Source origin is not approved")
    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Source must resolve to public addresses")
    # Pin the validated DNS answer for this connection to prevent DNS rebinding.
    address = addresses[0][4][0]
    host = parts.hostname
    destination = url.replace(parts.netloc, f"[{address}]" if ":" in address else address, 1)
    if parts.port:
        destination = url.replace(
            parts.netloc, (f"[{address}]" if ":" in address else address) + f":{parts.port}", 1
        )
    with httpx.Client(follow_redirects=False, trust_env=False, timeout=20) as client:  # noqa: SIM117
        with client.stream(
            "GET", destination, headers={"Host": parts.netloc}, extensions={"sni_hostname": host}
        ) as response:
            if response.status_code != 200:
                raise ValueError(f"Source returned HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "").split(";")[0]
            chunks = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 2_000_000:
                    raise ValueError("Source exceeds 2 MB bound")
                chunks.append(chunk)
    return ingestor.ingest(
        source_document(
            b"".join(chunks),
            {**metadata, "source": url, "provenance_kind": "external"},
            content_type=content_type,
        ),
        scope,
    )
