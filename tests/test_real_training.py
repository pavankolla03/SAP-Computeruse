import json
import pytest
from PIL import Image
from sap_cua.training.sft import SFTConfig, SFTTrainer, load_dataset, single_example_collator
from sap_cua.model.opencua import parse_action, resized_dimensions


def dataset(tmp_path):
    records = []
    for i, split in enumerate(("train", "validation", "test")):
        image = f"{i}.png"
        Image.new("RGB", (112, 112), color=(i * 80, 20, 30)).save(tmp_path / image)
        records.append(
            {
                "image_path": image,
                "instruction": "Click Deploy",
                "response": "pyautogui.click(28, 28)",
                "family": f"family-{i}",
                "split": split,
                "verified": True,
                "image_sanitized": True,
                "source": "sandbox",
            }
        )
    path = tmp_path / "dataset.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in records))
    return path, records


def test_dataset_fingerprint_includes_images(tmp_path):
    path, _ = dataset(tmp_path)
    splits, manifest = load_dataset(str(path))
    assert manifest["counts"] == {"train": 1, "validation": 1, "test": 1}
    Image.new("RGB", (112, 112), "white").save(tmp_path / "0.png")
    assert load_dataset(str(path))[1]["sha256"] != manifest["sha256"]


@pytest.mark.parametrize("change", ["family", "screenshot", "unverified", "secret", "path"])
def test_dataset_rejects_leakage_unreviewed_secrets_and_escape(tmp_path, change):
    path, rows = dataset(tmp_path)
    if change == "family":
        rows[1]["family"] = rows[0]["family"]
    if change == "screenshot":
        rows[1]["image_path"] = rows[0]["image_path"]
    if change == "unverified":
        rows[0]["verified"] = False
    if change == "secret":
        rows[0]["instruction"] = "password=secret123456"
    if change == "path":
        rows[0]["image_path"] = "../outside.png"
        Image.new("RGB", (112, 112)).save(tmp_path.parent / "outside.png")
    path.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError):
        load_dataset(str(path))


def test_validation_writes_no_fake_weights_or_losses(tmp_path):
    path, _ = dataset(tmp_path)
    trainer = SFTTrainer(SFTConfig(dataset_path=str(path), output_dir=str(tmp_path / "out")))
    result = trainer.dry_run()
    assert result["trained"] is False and "train_loss" not in result
    assert not (tmp_path / "out").exists()
    with pytest.raises(RuntimeError):
        trainer.save_model()
    with pytest.raises(FileNotFoundError):
        trainer.resume_from_checkpoint(str(tmp_path))


def test_missing_dataset_never_synthesized(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_dataset(str(tmp_path / "missing.jsonl"))


def test_rl_no_fabricated_metrics(tmp_path):
    from sap_cua.training.rl import RLTrainer

    with pytest.raises(NotImplementedError):
        RLTrainer("base", str(tmp_path)).train()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "code",
    [
        "__import__('os').system('touch /tmp/unsafe')",
        "pyautogui.click(4,5); pyautogui.click(6,7)",
        "pyautogui.click(-1,10)",
        "pyautogui.click(112,10)",
        "pyautogui.click(x=10,y=True)",
        "pyautogui.click(5,6,x=10)",
        "pyautogui.click(**dict(x=10,y=10))",
    ],
)
def test_action_parser_rejects_unsafe_or_ambiguous_python(code):
    with pytest.raises((ValueError, TypeError)):
        parse_action(code, 112, 112)


def test_coordinates_match_processor_frame():
    w, h = resized_dimensions(1440, 900)
    assert w % 28 == 0 and h % 28 == 0
    action = parse_action(f"```python\npyautogui.click({w / 2}, {h / 2})\n```", w, h)
    assert action.gui_action.x == action.gui_action.y == 0.5
    assert action.confidence == 0


def test_single_sample_collator_does_not_pad_image_grid():
    assert single_example_collator([{"input_ids": [1]}]) == {"input_ids": [1]}
    with pytest.raises(ValueError):
        single_example_collator([{}, {}])
