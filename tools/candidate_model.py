"""Isolated local 4B/NF4 experiment; not a production model selector."""

import hashlib
import json
from pathlib import Path
import time
from PIL import Image
from cashproof.config import force_offline
from cashproof.errors import ProcessingError


class CandidateModel:
    def __init__(self, model_dir):
        force_offline()
        import torch
        from transformers import (
            AutoProcessor,
            Qwen3VLForConditionalGeneration,
            BitsAndBytesConfig,
        )
        from lmformatenforcer.integrations.transformers import (
            build_token_enforcer_tokenizer_data,
        )

        manifest = json.loads(
            (model_dir / "cashproof-manifest.json").read_text(encoding="utf-8")
        )
        revisions = {
            "Qwen/Qwen3-VL-2B-Instruct": "89644892e4d85e24eaac8bacfd4f463576704203",
            "Qwen/Qwen3-VL-4B-Instruct": "ebb281ec70b05090aa6165b016eac8ec08e71b17",
        }
        if (
            manifest["repo_id"] not in revisions
            or manifest["revision"] != revisions[manifest["repo_id"]]
        ):
            raise ValueError("Unexpected experimental checkpoint")
        expected = {
            "model-00001-of-00002.safetensors": "30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9",
            "model-00002-of-00002.safetensors": "046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6",
        }
        if manifest["repo_id"] == "Qwen/Qwen3-VL-2B-Instruct":
            expected = {
                "model.safetensors": "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0"
            }
        if not set(expected) <= {f["path"] for f in manifest["files"]}:
            raise ValueError("Missing pinned candidate weight entries")
        for item in manifest["files"]:
            path = (model_dir / item["path"]).resolve()
            if (
                not path.is_relative_to(model_dir.resolve())
                or path.stat().st_size != item["size"]
            ):
                raise ValueError("Candidate manifest path/size mismatch")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != item["sha256"] or (
                item["path"] in expected
                and digest.hexdigest() != expected[item["path"]]
            ):
                raise ValueError("Candidate checksum mismatch")
        self.manifest = manifest | {
            "experimental_recipe": {
                "adapter_sha256": hashlib.sha256(
                    Path(__file__).read_bytes()
                ).hexdigest(),
                "bitsandbytes": "0.48.1",
                "quantization": "NF4 double, BF16 compute, visual module unquantized",
                "image_max_edge": 848,
                "screening_max_pixels": 131072,
                "verification_max_pixels": 262144,
            }
        }
        self.version = (
            manifest["repo_id"]
            + "@"
            + manifest["revision"]
            + ";nf4-double;bnb=0.48.1;experimental"
        )
        self.runtime_configuration = {
            "image_max_edge": 848,
            "screening_max_pixels": 131072,
            "verification_max_pixels": 262144,
            "quantization": "NF4 double; visual module BF16; bitsandbytes 0.48.1",
            "screening_window_sec": 7,
            "screening_overlap_sec": 1,
            "verification_dense_radius_sec": 1,
            "max_images_per_call": 9,
            "max_input_tokens": 4608,
            "screening_mode": "assessments",
        }
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False
        )
        self.tokenizer_data = build_token_enforcer_tokenizer_data(
            self.processor.tokenizer
        )
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            llm_int8_skip_modules=["visual", "lm_head"],
        )
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.bfloat16,
            device_map="cuda:0",
            quantization_config=quantization,
            attn_implementation="sdpa",
        ).eval()

    def infer(self, frames, instruction, deadline, output_schema=None):
        if len(frames) > 9:
            raise ProcessingError("RESOURCE_EXHAUSTED", "Image budget exceeded")
        from lmformatenforcer import JsonSchemaParser, CharacterLevelParserConfig
        from lmformatenforcer.integrations.transformers import (
            build_transformers_prefix_allowed_tokens_fn,
        )

        content = []
        images = []
        try:
            for frame in frames:
                content.extend(
                    [
                        {
                            "type": "text",
                            "text": f"Frame {frame['id']} at {frame['timestamp_sec']:.6f} seconds",
                        },
                        {"type": "image"},
                    ]
                )
                image = Image.open(frame["path"]).convert("RGB")
                image.thumbnail((848, 848))
                images.append(image)
            content.append({"type": "text", "text": instruction})
            messages = [
                {
                    "role": "system",
                    "content": "Inspect the images as a factual observer. Report only visible actions and temporal context. Do not infer identity, intent, permission, audio, ledger correctness or legal guilt. Return strict JSON.",
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
                    "max_pixels": 262144 if "Candidate=" in instruction else 131072,
                },
            ).to("cuda:0")
            if inputs["input_ids"].shape[-1] > 4608:
                raise ProcessingError(
                    "RESOURCE_EXHAUSTED", "Input token budget exceeded"
                )
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded")
            kwargs = {}
            if output_schema:
                kwargs["prefix_allowed_tokens_fn"] = (
                    build_transformers_prefix_allowed_tokens_fn(
                        self.tokenizer_data,
                        JsonSchemaParser(
                            output_schema,
                            config=CharacterLevelParserConfig(
                                force_json_field_order=True
                            ),
                        ),
                    )
                )
            with self.torch.inference_mode():
                generated = self.model.generate(
                    **inputs,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                    top_k=None,
                    max_new_tokens=1024 if "Candidate=" in instruction else 768,
                    max_time=remaining,
                    use_cache=True,
                    **kwargs,
                )
            return self.processor.batch_decode(
                generated[:, inputs["input_ids"].shape[-1] :], skip_special_tokens=True
            )[0]
        finally:
            for image in images:
                image.close()
