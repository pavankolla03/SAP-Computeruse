"""Reduced random architecture contract test, NOT full 7B model evaluation."""

import argparse
import json
import torch
from PIL import Image
from transformers import AutoConfig, AutoModel
from peft import LoraConfig, get_peft_model
from sap_cua.model.opencua import OpenCUARuntime

parser = argparse.ArgumentParser()
parser.add_argument("--model-path", required=True)
args = parser.parse_args()
runtime = OpenCUARuntime(args.model_path)
sample = runtime.prepare(Image.new("RGB", (112, 112)), "Click Deploy", "pyautogui.click(28,28)")
config = AutoConfig.from_pretrained(args.model_path, trust_remote_code=True, local_files_only=True)
config.text_config.hidden_size = 32
config.text_config.intermediate_size = 64
config.text_config.num_hidden_layers = 1
config.text_config.num_attention_heads = 4
config.text_config.num_key_value_heads = 2
config.vision_config.hidden_size = 32
config.vision_config.intermediate_size = 64
config.vision_config.depth = 1
config.vision_config.num_heads = 4
config.vision_config.out_hidden_size = 32
config.vision_config.fullatt_block_indexes = [0]
model = AutoModel.from_config(config, trust_remote_code=True, attn_implementation="sdpa")
lora = get_peft_model(
    model,
    LoraConfig(
        r=2,
        lora_alpha=4,
        target_modules=r"language_model\.model\.layers\.\d+\.self_attn\.(q_proj|v_proj)",
    ),
)
optimizer = torch.optim.AdamW(lora.parameters(), lr=1e-3)
before = {k: v.detach().clone() for k, v in lora.named_parameters() if v.requires_grad}
loss = lora(**sample).loss
assert torch.isfinite(loss)
loss.backward()
optimizer.step()
changed = [k for k, v in lora.named_parameters() if k in before and not torch.equal(v, before[k])]
assert changed
result = model.generate(
    **{k: v for k, v in sample.items() if k != "labels"}, max_new_tokens=2, do_sample=False
)
assert result.shape[1] == sample["input_ids"].shape[1] + 2
print(
    json.dumps(
        {
            "contract_only": True,
            "random_reduced_model": True,
            "full_7b_trained": False,
            "image_input": True,
            "finite_loss": True,
            "lora_weights_changed": len(changed),
            "generation": True,
        },
        indent=2,
    )
)
