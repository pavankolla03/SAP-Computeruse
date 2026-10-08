"""Collect verified synthetic browser trajectories; never label them as real SAP.

Start sap-cua serve first. Run with --url http://127.0.0.1:8000.
Data remains local; it is not uploaded, trained, or promoted automatically.
"""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from sap_cua.runtime.browser import BrowserExecutor
from sap_cua.model.opencua import resized_dimensions
from sap_cua.training.sft import load_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default=".sap-cua/sapworld-data")
    args = parser.parse_args()
    if urlsplit(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("This collector operates only on the local synthetic fixture")
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / "dataset.jsonl").exists():
        parser.error("Dataset already exists; use a new output directory")
    records = []
    trajectories = []
    with BrowserExecutor(allowed_origins=[args.url], screenshot_dir=str(out)) as browser:
        browser.navigate(args.url)
        for family in range(12):
            split = "train" if family < 8 else "validation" if family < 10 else "test"
            browser.navigate(args.url + "/assets/sapworld.html?family=workflow-" + str(family))
            browser.wait_for("#create-package")
            steps = []
            tasks = [
                ("#create-package", "Create the package.", lambda s: s["package"] == "Demo"),
                ("#create-flow", "Create the integration flow.", lambda s: s["flow"] == "Hello"),
                (
                    "#deploy",
                    "Deploy the integration flow.",
                    lambda s: s["deployed"] is True and s["message"] is None,
                ),
                (
                    "#test-flow",
                    "Run a test message.",
                    lambda s: s["message"] is not None and s["message"]["status"] == "COMPLETED",
                ),
            ]
            for index, (selector, instruction, verify) in enumerate(tasks):
                target = browser._page.locator(selector)
                target.scroll_into_view_if_needed()
                frame = target.bounding_box()
                size = browser._page.viewport_size
                # Capture the ACTUAL pre-action browser pixels and transformed target point.
                filename = f"images/{family:02}-{index:02}.png"
                browser.screenshot(str(out / filename))
                w, h = resized_dimensions(size["width"], size["height"])
                x = (frame["x"] + frame["width"] / 2) / size["width"] * w
                y = (frame["y"] + frame["height"] / 2) / size["height"] * h
                response = f"pyautogui.click({x:.3f}, {y:.3f})"
                browser.click(selector)
                state = browser._page.evaluate("window.sapworldState")
                assert verify(state), state
                row = {
                    "image_path": filename,
                    "instruction": instruction,
                    "response": response,
                    "family": f"synthetic-workflow-{family}",
                    "split": split,
                    "verified": True,
                    "image_sanitized": True,
                    "source": "sandbox",
                }
                records.append(row)
                steps.append({"sample": filename, "verification": state, "success": True})
            trajectories.append(
                {"family": family, "source": "sandbox", "steps": steps, "success": True}
            )
    dataset = out / "dataset.jsonl"
    dataset.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    _, manifest = load_dataset(str(dataset))
    manifest.update(source="synthetic_sapworld", real_sap=False, performance_evidence=False)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "trajectories.json").write_text(json.dumps(trajectories, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
