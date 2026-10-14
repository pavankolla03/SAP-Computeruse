# SAP DEV deployment workflow

The local workbench supports an explicit exported-template workflow: configure a DEV connection, import a reviewed iFlow ZIP, inspect the rendered artifact and test contract, then start a background job that uploads, deploys, sends one test, and verifies its message log. This orchestration is covered by simulated HTTP/API contracts; it has **not been validated against this user's live SAP tenant**. A successful sandbox plan is separate evidence.

## 1. Configure the connection

In the connection panel, enter the DEV management API root ending in `/api/v1`, OAuth token endpoint, client ID and client secret from your service key. Supply a separate runtime HTTPS origin and runtime OAuth credentials with permission to invoke the selected sender endpoint. The runtime origin has no path; the allowed test prefix defaults to `/http/` and can be restricted further.

Saving browser-supplied credentials keeps them in the server process only. The API returns presence flags, never the credential values. Restarting the process forgets them. Blank credential fields preserve the existing value only when the endpoint and principal are unchanged; changing either requires the new credentials. A connection change invalidates already-reviewed plans. Active operations hold the connection stable until they finish.

For unattended local startup, the `.env.example` variables provide equivalent configuration. Credentials supplied this way persist in the ignored `.env` or your external environment; they are **not** made memory-only by the application. Docker Compose forwards these variables at runtime without baking them into the image. Keep populated `.env` files and service keys outside Git and chat.

Run the read-only probe. It checks access to package, runtime-artifact and message-log resources, and cannot certify whether a supplied host is a DEV tenant or whether write permissions are available. The DEV designation is the operator's assertion. Enable DEV writes only for the tenant and scope you intend to use; the default is disabled. Runtime credentials are never silently copied from the management connection.

## 2. Import a reviewed iFlow export

In SAP Integration Suite, open the integration package's **Artifacts** list and use **Actions → Download** for the chosen integration flow. Import the artifact ZIP, rather than a package ZIP containing nested artifacts. SAP documents this export procedure in its [Integration Suite artifacts guide](https://help.sap.com/docs/continuous-integration-and-delivery/sap-continuous-integration-and-delivery/3daf56d952c74c10b0be810d082e68ab.html).

Review the complete flow and its scripts, endpoints, managed credential references, side effects, sender authorization and test behavior before checking the import approval box. Use synthetic test data. Approval means the exact archive hash is accepted by the operator; valid XML does not prove SAP runtime compatibility or certify arbitrary embedded code as safe.

The importer accepts reviewable UTF-8 source files, rejects opaque binaries, encrypted entries and symbolic links, and enforces archive/expanded-size limits, duplicate/path checks and safe XML parsing. This restricted format intentionally excludes exports containing JARs, binary certificates or other opaque resources. Potential credential material is rejected, but pattern detection is not proof that an artifact contains no secret. Store real secrets in SAP-managed credential artifacts and reference their aliases.

Custom placeholders use the exact syntax `{{PARAM_NAME}}` with uppercase names in `.xml` or `.iflw` files. Provide every discovered value, and do not supply unused keys. Values are XML-escaped. The renderer does **not** configure arbitrary SAP-native externalized properties or placeholders in `.prop`, Groovy or other files. An unmodified export without these placeholders can be imported with an empty parameter map. The approved template defines the whole integration; natural-language sandbox plans do not generate live iFlow ZIPs.

## 3. Set a functional test contract

Choose a package ID, the intended iFlow ID, a display name, and the runtime sender path under the configured prefix. If the export declares a `Bundle-SymbolicName` in its manifest, the selected iFlow ID must match it; the UI fills that ID automatically. The application preserves this native identity and does not silently clone or rename SAP artifacts. An archive without a declared manifest identity remains unvalidated until SAP accepts it. The job rejects an existing iFlow instead of overwriting it. Review every downstream action of the imported flow before sending the test.

The current test supports one POST with a UTF-8 body of at most 65,536 bytes, a JSON/XML/plain-text content type, an expected 2xx status, and a nonblank response substring assertion. It does not infer arbitrary business correctness from an HTTP success code. Test input and the assertion are stored with the private plan, so supply synthetic, non-sensitive data; response bodies are not persisted.

The approved flow must return its **own current** message-log ID in the response header `SAP_MessageProcessingLogID` (header matching is case-insensitive). SAP documents this framework-provided ID as a read-only header/property in [Headers and Exchange Properties Provided by the Integration Framework](https://help.sap.com/docs/cloud-integration/sap-cloud-integration/headers-and-exchange-properties-provided-by-integration-framework). Configure the flow's response contract to expose that value and verify the actual response in your tenant. An internal property being present does not establish that a particular adapter returns it automatically. The application does not invent an ID, substitute a predecessor/correlation ID, or select the latest unrelated message.

## 4. Review and execute

Create a plan, inspect its steps and configuration blockers, and download the rendered ZIP for review. The plan binds the approved archive, rendered archive, exact test request and connection revision. Explicitly start the reviewed plan when it is ready.

The background job performs these stages:

1. Probe DEV access and confirm that the selected iFlow does not already exist.
2. Observe the selected package or create it if absent, then independently verify its identity.
3. Upload the rendered artifact and verify the design-time iFlow identity.
4. Request deployment, observe a successful build and the matching started runtime artifact.
5. Send the test once and check the response status, required text and message-log ID.
6. Query that exact message log and verify the selected iFlow, fresh timezone-aware timestamps and completed status.

One live job runs at a time. The reviewed job has a 300-second overall budget checked between operations, with bounded HTTP responses and polling; an in-flight request may finish after a cancellation or budget boundary. Refreshing the browser retains the durable run and its evidence. Requests with uncertain write outcomes are not retried automatically. Cancel stops future stages when control returns from an in-flight request; it cannot undo a completed upload, deployment or business action. Restart recovery marks abandoned work interrupted and does not replay it. Review evidence and any created resources before starting a new plan.

Download the sanitized evidence after completion. A successful result establishes this test contract and correlated message processing, not all possible payloads or business transactions. When RAG is available, a successful run can contribute a scoped sanitized summary; retrieval never authorizes a deployment.

## Current boundaries and validation

The workflow has no production mode, overwrite, automatic undeploy/delete, rollback, or automatic repair path. The selected iFlow can itself have side effects, so using a DEV connection is not sufficient to make any arbitrary export harmless. Hosted multiuser identity, tenant row-level database security and real SAP GUI selector coverage remain separate deployment work.

The knowledge database and CPU model initialization run in the background so a retrieval setup failure does not prevent connection setup or live evidence access. The live workflow requires an operator-approved export and valid tenant credentials. An official SAP CodeJam package was inspected as a potential starter, but it has business-service and input assumptions and was not shipped as a generic echo template. See [sample research and supported planner intents](PLANNER_SUPPORTED_INTENTS.md).

Unit and mocked HTTP/API tests exercise profile isolation, invalid configuration, connection changes, failed/uncertain calls, archive integrity, run replay prevention, cancellation, response assertions and MPL verification. Current release totals and browser evidence are recorded in [STATUS](STATUS.md). Live tenant acceptance, sender response-header behavior and the supplied business test remain unvalidated until they are exercised with the user's DEV access.
