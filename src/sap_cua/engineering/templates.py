"""Validate/parameterize approved exported iFlow ZIPs; never invent SAP deployment files."""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath
from xml.sax.saxutils import escape

from defusedxml import ElementTree

CANONICAL_TEMPLATES = {
    "HTTPS_TO_HTTP": ("HTTPS", "HTTP"),
    "HTTPS_TO_ODATA_V2": ("HTTPS", "ODataV2"),
    "HTTPS_TO_ODATA_V4": ("HTTPS", "ODataV4"),
    "SFTP_TO_ODATA": ("SFTP", "ODataV4"),
    "SOAP_TO_REST": ("SOAP", "HTTP"),
    "JMS_RETRY": ("JMS", "HTTP"),
    "EVENT_MESH_ASYNC": ("EventMesh", "HTTP"),
    "PROCESSDIRECT_LAYERED": ("ProcessDirect", "ProcessDirect"),
    "ERROR_HANDLING_STANDARD": ("HTTPS", "HTTP"),
}


def blueprint(name: str):
    if name not in CANONICAL_TEMPLATES:
        raise ValueError("Unknown canonical template")
    sender, receiver = CANONICAL_TEMPLATES[name]
    return {
        "name": name,
        "artifact_status": "requires_approved_sap_export",
        "required_adapters": [sender, receiver],
        "parameters": ["RECEIVER_URL", "CREDENTIAL_ALIAS"],
        "security_requirements": ["managed credential reference", "approved endpoint"],
        "validation_rules": [
            "valid iFlow XML",
            "no unresolved parameters",
            "tenant upload validation",
            "functional test plus correlated MPL",
        ],
        "nodes": ["Start", "Transform", "Receiver", "End"],
        "deployable": False,
    }


class IFlowTemplateEngine:
    def render(self, archive: bytes, parameters: dict[str, str], *, approved_sha256: str):
        if hashlib.sha256(archive).hexdigest() != approved_sha256:
            raise PermissionError("Template does not match the approved artifact hash")
        if len(archive) > 20_000_000:
            raise ValueError("Template exceeds archive limit")
        if any(
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,60}", key)
            or not isinstance(value, str)
            or len(value) > 4000
            or "\n" in value
            or "\r" in value
            for key, value in parameters.items()
        ):
            raise ValueError("Invalid template parameter")
        out = io.BytesIO()
        used = set()
        flow_files = 0
        total = 0
        names = set()
        with (
            zipfile.ZipFile(io.BytesIO(archive)) as source,
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
        ):
            if len(source.infolist()) > 1000:
                raise ValueError("Too many archive entries")
            for info in source.infolist():
                path = PurePosixPath(info.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in info.filename
                    or info.filename in names
                ):
                    raise ValueError("Unsafe or duplicate archive entry")
                names.add(info.filename)
                total += info.file_size
                if total > 100_000_000 or info.file_size > 20_000_000:
                    raise ValueError("Expanded artifact exceeds limit")
                data = source.read(info)
                if path.suffix in (".xml", ".iflw"):
                    text = data.decode("utf-8")
                    placeholders = set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", text))
                    if placeholders - set(parameters):
                        raise ValueError("Missing externalized parameter values")
                    for key in placeholders:
                        text = text.replace(
                            "{{" + key + "}}",
                            escape(parameters[key], {'"': "&quot;", "'": "&apos;"}),
                        )
                    ElementTree.fromstring(text)
                    data = text.encode()
                    used |= placeholders
                    flow_files += path.suffix == ".iflw"
                target.writestr(info, data)
        if not flow_files:
            raise ValueError("Exported artifact contains no .iflw definition")
        if set(parameters) - used:
            raise ValueError("Supplied parameter was not found in approved template")
        return {
            "artifact": out.getvalue(),
            "sha256": hashlib.sha256(out.getvalue()).hexdigest(),
            "validated_xml": True,
            "tenant_validated": False,
        }
