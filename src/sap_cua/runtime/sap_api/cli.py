"""Read-only SAP readiness and evidence commands. No mutations are enabled here."""

import argparse
import json
from datetime import datetime

from sap_cua.runtime.sap_api import SAPAPIClient
from sap_cua.runtime.sap_api.connection import connection_status, probe_configured_connection
from sap_cua.runtime.sap_api.verification import verify_deployment, verify_message


def main(argv):
    parser = argparse.ArgumentParser(prog="sap-cua sap")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show missing configuration names without contacting SAP")
    sub.add_parser("probe", help="Check read access to packages, runtime artifacts and MPL")
    deployment = sub.add_parser(
        "verify-deployment", help="Observe a known deployment task and runtime state"
    )
    deployment.add_argument("iflow_id")
    deployment.add_argument("--task-id", required=True)
    deployment.add_argument("--timeout", type=float, default=60)
    message = sub.add_parser(
        "verify-message", help="Verify one fresh message for the expected iFlow"
    )
    message.add_argument("iflow_id")
    message.add_argument("--message-id", required=True)
    message.add_argument("--not-before", type=datetime.fromisoformat, required=True)
    args = parser.parse_args(argv)
    if args.command == "status":
        result = connection_status()
        print(json.dumps(result, indent=2))
        return 0 if result["configured"] else 1
    if args.command == "probe":
        result = probe_configured_connection()
    else:
        status = connection_status()
        if not status["configured"]:
            print(json.dumps(status, indent=2))
            return 1
        with SAPAPIClient(allow_mutations=False, timeout_seconds=10) as client:
            if args.command == "verify-deployment":
                result = verify_deployment(
                    client, args.iflow_id, args.task_id, timeout=args.timeout
                )
            else:
                result = verify_message(client, args.iflow_id, args.message_id, args.not_before)
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1
