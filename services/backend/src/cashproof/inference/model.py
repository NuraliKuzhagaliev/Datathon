from pathlib import Path
import json
import time
from PIL import Image
from ..config import force_offline
from ..errors import ProcessingError


class LocalQwen:
    def __init__(self, model_dir: Path):
        force_offline()
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required on the qualified host")
        manifest = json.loads(
            (model_dir / "cashproof-manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest["repo_id"] != "Qwen/Qwen3-VL-2B-Instruct"
            or len(manifest["revision"]) != 40
        ):
            raise ValueError("A pinned official model is required")
        # Provisioning verifies weights; runtime checks sizes and local-only loading.
        for item in manifest["files"]:
            file = (model_dir / item["path"]).resolve()
            if (
                not file.is_relative_to(model_dir.resolve())
                or file.stat().st_size != item["size"]
            ):
                raise ValueError("Model manifest mismatch")
        self.version = f"{manifest['repo_id']}@{manifest['revision']}"
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False
        )
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            device_map="cuda:0",
            attn_implementation="sdpa",
        ).eval()

    def infer(self, frames, instruction, deadline):

        content, images = [], []
        for frame in frames:
            content.append(
                {
                    "type": "text",
                    "text": f"Frame {frame['id']} at {frame['timestamp_sec']:.6f} seconds",
                }
            )
            content.append({"type": "image"})
            image = Image.open(frame["path"]).convert("RGB")
            image.thumbnail((448, 448))  # preserves aspect, never upscales
            images.append(image)
        content.append({"type": "text", "text": instruction})
        messages = [
            {
                "role": "system",
                "content": "Inspect only visible actions. No identity, intent, audio, ledger claims or invented rules. Return strict JSON only.",
            },
            {"role": "user", "content": content},
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text], images=images, return_tensors="pt", padding=True
        ).to("cuda:0")
        if inputs["input_ids"].shape[-1] > 14000:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED", "Bounded model context exceeded"
            )
        remaining = deadline - time.time()
        if remaining <= 0:
            raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded")
        with self.torch.inference_mode():
            ids = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=768,
                max_time=remaining,
                use_cache=True,
            )
        result = self.processor.batch_decode(
            ids[:, inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        )[0]
        for image in images:
            image.close()
        return result
