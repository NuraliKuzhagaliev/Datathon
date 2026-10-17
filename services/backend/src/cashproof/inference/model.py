from pathlib import Path
import hashlib
import json
import time
from PIL import Image
from ..config import force_offline
from ..errors import ProcessingError
from .. import __version__


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
            or manifest["revision"] != "89644892e4d85e24eaac8bacfd4f463576704203"
        ):
            raise ValueError("A pinned official model is required")
        # Verify exact bytes before loading. Hashes detect changes relative to
        # the pinned manifest; they are not an authenticity claim about footage.
        for item in manifest["files"]:
            file = (model_dir / item["path"]).resolve()
            if (
                not file.is_relative_to(model_dir.resolve())
                or file.stat().st_size != item["size"]
            ):
                raise ValueError("Model manifest mismatch")
            digest = hashlib.sha256()
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != item["sha256"]:
                raise ValueError("Model checksum mismatch")
        weight = next(
            item for item in manifest["files"] if item["path"] == "model.safetensors"
        )
        if (
            weight["sha256"]
            != "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0"
        ):
            raise ValueError("Weight revision is not the qualified checkpoint")
        self.version = (
            f"{manifest['repo_id']}@{manifest['revision']};backend={__version__}"
        )
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
        if len(frames) > 16:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED", "Per-call image budget exceeded"
            )
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
            text=[text],
            images=images,
            return_tensors="pt",
            padding=True,
            images_kwargs={
                "min_pixels": 1024,
                "max_pixels": 131072 if "Candidate=" in instruction else 65536,
            },
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
                temperature=None,
                top_p=None,
                top_k=None,
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
