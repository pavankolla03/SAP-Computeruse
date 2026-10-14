# Supported requirement language

The current requirement compiler is deterministic. Retrieval adds scoped evidence and approved naming standards; it does not turn arbitrary prose into executable integrations.

A construction request must specify one sender followed by one receiver. Introductory words such as “Please create an integration flow from” are accepted. For example:

- `Create a JMS to HTTP integration flow`
- `Please create a SOAP to REST integration`
- `Create HTTPS Router Content Modifier to OData V4`
- `Create HTTPS with JMS retry to HTTP`

Sender adapters: HTTPS (also written HTTP or REST), SFTP, SOAP, JMS, Event Mesh. Receiver adapters: HTTP (also HTTPS or REST), SOAP, OData V2, OData V4. Bare OData means V2. These are adapter names, not assurances that a live tenant has the capabilities or credentials configured.

Components are inserted in the requested order: Content Modifier, Router, Splitter, JMS retry, Exception Subprocess (also “error handling”). Repeated components require a richer typed contract and are blocked. JMS retry is a component, not a JMS sender.

Missing endpoints, more than two endpoint adapters, unsupported adapter directions, negation, custom methods or URLs, schedules, arbitrary code, and other unimplemented clauses produce a blocked plan with no construction steps. This prevents a plausible but different flow from appearing as a successful compilation. Use an approved exported iFlow and typed deployment configuration for live work; a sandbox plan does not prove SAP deployment.

Package creation and known-error diagnosis retain their existing separate compiler paths. The supported flow examples are deliberately narrow, and a free-form business requirement may need a new reviewed construction contract.

# Public export research

An official source was inspected on 13 October 2026: [SAP CodeJam export at pinned commit](https://github.com/SAP-samples/connecting-systems-services-integration-suite-codejam/blob/b4fbfeb2d0c1fc6e6e94874e88e3dd2ece513f00/assets/cloud-integration/Connecting%20Systems%20CodeJam%20-%20Export.zip). The repository declares Apache-2.0 in its [LICENSE](https://github.com/SAP-samples/connecting-systems-services-integration-suite-codejam/blob/b4fbfeb2d0c1fc6e6e94874e88e3dd2ece513f00/LICENSE) and [REUSE metadata](https://github.com/SAP-samples/connecting-systems-services-integration-suite-codejam/blob/b4fbfeb2d0c1fc6e6e94874e88e3dd2ece513f00/REUSE.toml).

The 49,204-byte package contains nested iFlow archives. The baseline `a7049e470648484fada294359ac89f6d_content` includes the SAP IntegrationFlow manifest, `.project`, parameter files, and BPMN `.iflw`. It has an HTTPS sender, HTTP GET receiver to SAP's S/4 mock BusinessPartners service, JSON-to-XML conversion, and an `employee_id` property derived from its input. Later variants add Groovy and other integrations.

This is a useful structural reference but is not a generic smoke flow: its remote service and input assumptions need explicit adaptation. No external sample was bundled or executed as part of this inspection, and no tenant validity is claimed. Any redistribution must preserve the applicable license and attribution; use of SAP services requires the user's own access.
