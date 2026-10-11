# Knowledge and saved-run workflow

## Add knowledge

Open **Knowledge → Add approved knowledge to this workspace**. Supply a title,
source reference, collection, version and plain text (up to 25,000 characters).
Confirm that the text is permitted and approved for use in this workspace, then
select **Add knowledge**. Secret sanitization runs before embedding and storage.
Do not paste credentials; pattern-based sanitization cannot identify every secret.

Customer, tenant, security classification and document identity are assigned by
the server. The form cannot create verified execution memories, inject structured
planner facts, index global content, or choose another tenant. Viewer roles cannot
import. Source references are labels/provenance; the form never fetches a URL.

The same title and source identify a document. Submitting the same version/content
is a no-op. Changed content, source version or collection creates a new indexed
version while retaining prior versions. Changing the title or source creates a
separate document. Approved notes are treated as data, not runtime instructions.

Search supports automatic domain routing or an explicit collection. General SAP
and Integration Suite documents now participate in automatic routing alongside
specialized collections.

## Reopen a saved plan

Generate a plan, then return to it through **Run history → Open plan**, even after
refreshing the browser. Review its actions and sources before running it. Blocked
plans remain blocked. Running/completed/failed/interrupted records are view-only;
the server's atomic claim prevents replay or concurrent duplicate execution.

Editing the requirement invalidates the current plan. A delayed response for an
older requirement cannot restore execution. Opening another record also invalidates
pending plan responses. Requirement editing and plan generation are disabled while
execution is in progress.

## Download evidence

Open a run and select **Download run evidence (JSON)**. New execution records retain
the entire semantic plan alongside actions, verification results, sources, recovery
attempts and usage. Older records remain readable when a plan is absent. Downloads
and history details enforce the configured tenant scope and sanitize records again
before returning them, including records created before current sanitization rules.

The UI and export do not turn a simulator result into a live SAP result. Real DEV
credentials, tenant validation and approved artifacts are still required.
