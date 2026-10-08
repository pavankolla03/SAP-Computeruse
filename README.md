# SAP-CUA

A local workbench and research runtime for an SAP-specialized computer-use agent.
OpenCUA-7B is the base model. This repository does **not yet contain a SAP-fine-tuned
checkpoint or evidence of superiority to other agents**.

## Run the application

Python 3.11 or 3.12 is required. The web UI has no Node dependency.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
sap-cua serve
```

Open http://127.0.0.1:8000. Click **Run workflow** to create a package, configure a
flow and verify deployment in the isolated local sandbox. Each run has a fresh
sandbox, saved action results and independent state verification. This example
is a scripted workflow; it is not a model benchmark or a live SAP deployment.

```sh
sap-cua run --example
sap-cua doctor
pytest -q
python -m build
```

## Model inference

```sh
pip install -e '.[ml,browser]'
sap-cua browser-install
sap-cua download-model --destination .models/OpenCUA-7B
sap-cua ground screenshot.png 'Click the Deploy button.' --model-path .models/OpenCUA-7B
```

The download pins `xlangai/OpenCUA-7B` to revision
`a2efb7d2b104d477a4a2666a357e79550a28aafc`, including its custom model/tokenizer code.
Only load checkpoints and Python model files you trust. `ground` predicts an action;
it does not execute it. Coordinates are normalized from the resized image frame.
Generated Python is parsed through a literal action allowlist, never executed.
Unrecognized or malformed output fails explicitly. Confidence is not calibrated.

A CUDA GPU is recommended. CPU inference uses a 6 GiB resident-weight budget with
disk offload; this saves memory but can be very slow. The 16 GB development Mac is
not a suitable full 7B training machine. `SAP_CUA_MODEL_PATH` selects the checkpoint.
An explicitly configured `SAP_CUA_INFERENCE_URL` can point to an OpenAI-compatible
OpenCUA server; screenshots are then sent to that server. No remote inference
service or paid GPU is provisioned automatically.

## Training

LoRA and 4-bit QLoRA use actual Transformers/PEFT optimization with image tensors,
masked prompt labels, language-only adapters, validation, checkpoints and dataset
fingerprints. There is no automatic synthetic-data fallback or fabricated loss.

```sh
sap-cua train sft --model-path .models/OpenCUA-7B --dataset data/examples.jsonl \
  --output checkpoints/run-001 --validate-only
# Run on an authorized, provisioned CUDA machine:
sap-cua train qlora --model-path .models/OpenCUA-7B --dataset data/examples.jsonl \
  --output checkpoints/run-001 --max-steps 100
```

Install `.[ml,qlora]` for CUDA QLoRA. No training is launched by the web UI.
Each JSONL row uses this schema (image paths are relative to the dataset directory):

```json
{"image_path":"images/001.png","instruction":"Click Deploy","response":"pyautogui.click(140, 140)","family":"deployment-a","split":"train","verified":true,"image_sanitized":true,"source":"human"}
```

Provide nonempty `train` and `validation` splits. A task family or identical screenshot
cannot cross splits. Action coordinates must match the processor's resized image.
The dataset author must actually verify the action and review/redact image secrets
before setting those booleans. Supported sources: `human`, `validated_teacher`,
`sandbox`. Sandbox examples must remain identifiable as synthetic. Automatic image
secret detection is not complete. Text secret checks are heuristic, not a guarantee.

## SAP and executor boundaries

The OAuth API client supports package operations, ZIP iFlow upload, deployment,
runtime status and MPL reads using Integration Suite resource names. It requires
`SAP_API_BASE_URL`, `SAP_TOKEN_URL`, `SAP_CLIENT_ID`, `SAP_CLIENT_SECRET` from the
environment. Keep secrets outside source control. Client mutations default to denied;
set `allow_mutations=True` only inside a separately authorized application context.
Tenant validation and CSRF behavior still need a real development tenant.

The hybrid router accepts explicitly registered executor bindings and a trusted
authorization callback. It derives risk from the DSL, not model-supplied labels,
and does not retry a write through another executor after a timeout. Playwright
uses a fresh browser, an explicit origin allowlist, masked sensitive fields, blocked
out-of-scope network requests, and bounded in-page actions. Native desktop control,
MCP connections and arbitrary code are not enabled in the workbench.

The web UI binds to loopback, checks Host and Origin, uses an HTTP-only local session,
and requires a custom header for writes. It is a local single-user tool, not an
internet-facing multi-user service. The Docker compose port also binds to loopback.

## Evaluation and remaining work

`sap-cua benchmark --levels 1,2` exercises the legacy SAPBench mock harness.
There are 101 task templates, but many are not executable end to end yet. Template
count and mock results are not evidence of real SAP or model performance.

See [status](docs/STATUS.md), [blockers](docs/BLOCKERS.md),
[phase roadmap](docs/ROADMAP.md), and [the original audit](docs/AUDIT_2026-10-07.md).
RL reward utilities, recovery/transition builders, model registry, and other legacy
modules are preserved for further work; several are scaffolds. RL optimization is
explicitly unavailable instead of returning fictional training metrics.

## Local browser fixture and data pipeline

With the server running, open `/assets/sapworld.html` to try the simplified package,
flow, deployment and test-message fixture. It distinguishes deployment from message
processing and resets without touching SAP. Collect actual screenshots and verified
click targets with:

```sh
python scripts/collect_sapworld.py --url http://127.0.0.1:8000 --output .sap-cua/examples
```

This produces 48 examples, recorded state evidence and a dataset fingerprint. The
split separates synthetic fixture variants; it is **not** a held-out SAP capability
benchmark and should not be used to claim generalization. The generic browser loop
accepts a model, an origin-scoped browser, caller-owned action authorization and an
independent verifier. It stops on denied actions, failure, or budget exhaustion.
