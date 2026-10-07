"""SAP mock environment for development and testing."""

from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from sap_cua.sap.actions import SAPActionType, ActionDefinition, get_action_definition
from sap_cua.types import SAPModule, Page, SAPState

logger = logging.getLogger(__name__)


class SAPMockEnvironment:
    """In-memory mock SAP Integration Suite environment."""

    def __init__(self, tenant_id: str = "dev-tenant-001") -> None:
        self.tenant_id = tenant_id
        self.packages: dict[str, dict[str, Any]] = {}
        self.iFlows: dict[str, dict[str, Any]] = {}
        self.security_materials: dict[str, dict[str, Any]] = {}
        self.api_proxies: dict[str, dict[str, Any]] = {}
        self.event_mesh_topics: dict[str, dict[str, Any]] = {}
        self.mpl_entries: list[dict[str, Any]] = []
        self.run_id = self._generate_run_id()
        self._counter = 0

    def _generate_run_id(self) -> str:
        return f"CUA_{uuid.uuid4().hex[:6].upper()}"

    def _generate_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self.run_id}_{self._counter:04d}"

    def reset(self) -> None:
        self.packages.clear()
        self.iFlows.clear()
        self.security_materials.clear()
        self.api_proxies.clear()
        self.event_mesh_topics.clear()
        self.mpl_entries.clear()
        self._counter = 0
        self.run_id = self._generate_run_id()

    def create_package(self, name: str, description: str = "") -> dict[str, Any]:
        pkg_id = name.upper().replace(" ", "_")
        if pkg_id in self.packages:
            return {"success": False, "error": f"Package {pkg_id} already exists"}
        self.packages[pkg_id] = {
            "id": pkg_id,
            "name": name,
            "description": description,
            "created_at": time.time(),
            "iFlows": [],
            "status": "ACTIVE",
        }
        logger.info("[MOCK] Created package: %s", pkg_id)
        return {"success": True, "package_id": pkg_id, "status": "ACTIVE"}

    def get_package(self, package_id: str) -> dict[str, Any] | None:
        return self.packages.get(package_id)

    def delete_package(self, package_id: str) -> dict[str, Any]:
        if package_id not in self.packages:
            return {"success": False, "error": f"Package {package_id} not found"}
        if self.packages[package_id]["iFlows"]:
            return {"success": False, "error": "Package contains iFlows"}
        del self.packages[package_id]
        return {"success": True}

    def create_iflow(self, package_id: str, name: str, template: str = "Empty") -> dict[str, Any]:
        if package_id not in self.packages:
            return {"success": False, "error": f"Package {package_id} not found"}
        iflow_id = name.upper().replace(" ", "_")
        if any(f"{pkg}:{iflow_id}" in self.iFlows for pkg in self.packages):
            return {"success": False, "error": f"iFlow {iflow_id} already exists"}
        key = f"{package_id}:{iflow_id}"
        self.iFlows[key] = {
            "id": iflow_id,
            "package_id": package_id,
            "name": name,
            "template": template,
            "senders": [],
            "receivers": [],
            "components": [],
            "status": "NOT_DEPLOYED",
            "created_at": time.time(),
        }
        self.packages[package_id]["iFlows"].append(iflow_id)
        logger.info("[MOCK] Created iFlow: %s in package %s", iflow_id, package_id)
        return {"success": True, "iflow_id": iflow_id, "key": key}

    def deploy_iflow(self, package_id: str, iflow_id: str) -> dict[str, Any]:
        key = f"{package_id}:{iflow_id}"
        iflow = self.iFlows.get(key)
        if not iflow:
            return {"success": False, "error": f"iFlow {key} not found"}
        iflow["status"] = "DEPLOYED"
        iflow["deployed_at"] = time.time()
        logger.info("[MOCK] Deployed iFlow: %s", key)
        return {"success": True, "status": "DEPLOYED"}

    def add_sender(self, package_id: str, iflow_id: str, adapter: str, config: dict) -> dict:
        key = f"{package_id}:{iflow_id}"
        iflow = self.iFlows.get(key)
        if not iflow:
            return {"success": False, "error": f"iFlow {key} not found"}
        sender = {"adapter": adapter, "config": config, "id": f"sender_{len(iflow['senders'])+1}"}
        iflow["senders"].append(sender)
        return {"success": True, "sender_id": sender["id"]}

    def add_receiver(self, package_id: str, iflow_id: str, adapter: str, config: dict) -> dict:
        key = f"{package_id}:{iflow_id}"
        iflow = self.iFlows.get(key)
        if not iflow:
            return {"success": False, "error": f"iFlow {key} not found"}
        receiver = {"adapter": adapter, "config": config, "id": f"receiver_{len(iflow['receivers'])+1}"}
        iflow["receivers"].append(receiver)
        return {"success": True, "receiver_id": receiver["id"]}

    def add_component(self, package_id: str, iflow_id: str, component_type: str, config: dict) -> dict:
        key = f"{package_id}:{iflow_id}"
        iflow = self.iFlows.get(key)
        if not iflow:
            return {"success": False, "error": f"iFlow {key} not found"}
        component = {
            "type": component_type,
            "config": config,
            "id": f"comp_{len(iflow['components'])+1}",
        }
        iflow["components"].append(component)
        return {"success": True, "component_id": component["id"]}

    def query_mpl(self, iflow_key: str | None = None) -> list[dict[str, Any]]:
        if iflow_key:
            return [e for e in self.mpl_entries if e.get("iflow") == iflow_key]
        return self.mpl_entries

    def _add_mpl_entry(self, iflow: str, status: str) -> None:
        self.mpl_entries.append({
            "id": f"mpl_{len(self.mpl_entries)+1}",
            "iflow": iflow,
            "status": status,
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4()),
        })

    def execute_action(self, action: SAPActionType, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a mock SAP action."""
        try:
            action = SAPActionType(action)
        except ValueError:
            return {"success": False, "error": f"Unknown action: {action}"}
        definition = get_action_definition(action)
        if definition is None:
            return {"success": False, "error": f"Unknown action: {action}"}

        missing = [a for a in definition.required_args if a not in args]
        if missing:
            return {"success": False, "error": f"Missing args: {missing}"}

        method_map = {
            SAPActionType.CREATE_PACKAGE: lambda: self.create_package(args["name"], args.get("description", "")),
            SAPActionType.DELETE_PACKAGE: lambda: self.delete_package(args["package_id"]),
            SAPActionType.CREATE_IFLOW: lambda: self.create_iflow(args["package_id"], args["name"], args.get("template", "Empty")),
            SAPActionType.DEPLOY_IFLOW: lambda: self.deploy_iflow(args["package_id"], args["iflow_id"]),
            SAPActionType.ADD_SENDER: lambda: self.add_sender(args["package_id"], args["iflow_id"], args["adapter"], args.get("config", {})),
            SAPActionType.ADD_RECEIVER: lambda: self.add_receiver(args["package_id"], args["iflow_id"], args["adapter"], args.get("config", {})),
            SAPActionType.ADD_CONTENT_MODIFIER: lambda: self.add_component(args["package_id"], args["iflow_id"], "ContentModifier", args.get("config", {})),
            SAPActionType.ADD_ROUTER: lambda: self.add_component(args["package_id"], args["iflow_id"], "Router", args.get("config", {})),
            SAPActionType.QUERY_MPL: lambda: {"success": True, "entries": self.query_mpl(args.get("iflow_key"))},

        }
        handler = method_map.get(action)
        if handler:
            return handler()
        return {"success": False, "error": f"Mock action not implemented: {action.value}", "mock": True}


    def observe(self) -> dict[str, Any]:
        return {
            "mock": True,
            "tenant_id": self.tenant_id,
            "packages_count": len(self.packages),
            "iflows_count": len(self.iFlows),
            "state": "integration_design",
        }


def get_mock_environment(tenant_id: str = "dev-tenant-001") -> SAPMockEnvironment:
    return SAPMockEnvironment(tenant_id=tenant_id)
