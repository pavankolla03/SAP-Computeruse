# SAP DEV connection and verification

The local dashboard includes a **SAP DEV connection** panel. It reports which
configuration names are missing; it never returns client IDs, passwords, access
or CSRF tokens, message contents, or raw SAP responses.

Configure these values in the repository's ignored `.env` and restart the app:

- `SAP_API_BASE_URL`: the DEV API service root ending in `/api/v1`.
- `SAP_TOKEN_URL`: OAuth client-credentials token endpoint from the service key.
- `SAP_CLIENT_ID`: service-key client ID.
- `SAP_CLIENT_SECRET`: service-key client secret.

Keep real values outside chat and Git. Reuse the local database configuration
already installed on this machine. The dashboard does not accept API hosts or
credentials in request bodies. Its probe reads only the server configuration.

**Check read access** requests at most one package, runtime artifact and MPL entry.
The OAuth token request is a POST; SAP content requests are GETs. Successful
responses establish read access to those three resources only. They do not prove
tenant identity, DEV/production classification, create/deploy permission, or
functional business correctness. Credentials with denied access are not bypassed.

Equivalent commands:

```sh
sap-cua sap status
sap-cua sap probe
sap-cua sap verify-deployment FLOW_ID --task-id DEPLOYMENT_TASK_ID --timeout 60
sap-cua sap verify-message FLOW_ID --message-id MESSAGE_GUID --not-before 2026-10-10T01:00:00+00:00
```

The last two commands observe an existing operation; they do not deploy or send a
business message. Supply the actual identifiers and the trusted test start time.
The deployment verifier checks the build task, then the matching runtime artifact.
A successful build plus a started runtime is deployment readiness, not a completed
business test. Polling has a deadline and request-count limit; individual HTTP
requests retain their transport timeout, so an outstanding call can finish after
the observation deadline. Such late results cannot produce success.

The MPL verifier requires exactly one matching message, matching flow identity,
COMPLETED status, timezone-aware timestamps, a start no earlier than the test, and
an end no earlier than its start. ISO timestamps and SAP/OData millisecond dates
are supported. Payload correctness still requires an independent business assertion.

All live contracts remain unvalidated against this user's tenant because the DEV
service key and approved iFlow export have not been provided. The dashboard's
engineering executor remains sandbox-only.

Primary SAP references used for the contracts:

- [Build and deploy status](https://github.com/SAP-docs/btp-integration-suite/blob/main/docs/ci/Development/build-and-deploy-status-d8934e0.md)
- [Runtime status](https://github.com/SAP-docs/btp-integration-suite/blob/main/docs/ci/Operations/runtime-status-c14a7b1.md)
- [MPL query options](https://help.sap.com/docs/cloud-integration/sap-cloud-integration/query-options)
- [SAP monitoring model fields](https://help.sap.com/docs/SAP_ANALYTICS_CLOUD/42093f14b43c485fbe3adbbe81eff6c8/e9df42d2c6c44714b3d091b2d7b49cba.html)
