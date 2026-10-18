"""Allowlisted local NF4 experiments; never a production model selector."""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import time
from PIL import Image
from cashproof.config import force_offline
from cashproof.errors import ProcessingError


class CandidateModel:
    def __init__(self, model_dir, compact=False, native_video=False, precision="nf4"):
        if precision not in {"nf4", "bf16"}:
            raise ValueError("Unknown experimental precision")
        if native_video and not compact:
            raise ValueError("Native video requires the explicit compact experiment")
        self.native_video = native_video
        self.compact = compact
        self.technical_calls = []
        force_offline()
        import torch
        import transformers
        from transformers import AutoProcessor, BitsAndBytesConfig
        import lmformatenforcer.integrations.transformers as grammar

        grammar_sha256 = hashlib.sha256(Path(grammar.__file__).read_bytes()).hexdigest()

        manifest = json.loads(
            (model_dir / "cashproof-manifest.json").read_text(encoding="utf-8")
        )
        revisions = {
            "Qwen/Qwen3-VL-2B-Instruct": "89644892e4d85e24eaac8bacfd4f463576704203",
            "Qwen/Qwen3-VL-4B-Instruct": "ebb281ec70b05090aa6165b016eac8ec08e71b17",
            "Qwen/Qwen3.5-4B": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a",
        }
        if (
            manifest["repo_id"] not in revisions
            or manifest["revision"] != revisions[manifest["repo_id"]]
        ):
            raise ValueError("Unexpected experimental checkpoint")
        if precision == "bf16" and manifest["repo_id"] != "Qwen/Qwen3-VL-2B-Instruct":
            raise ValueError("Unquantized experiment is qualified for 2B only")
        quantization_description = (
            "NF4 double, BF16 compute, visual module unquantized"
            if precision == "nf4"
            else "BF16, no quantization"
        )
        expected = {
            "model-00001-of-00002.safetensors": "30a01a0556622645a3cce87b655bbbbbc1f170c196099f1b666c93202c3339a9",
            "model-00002-of-00002.safetensors": "046296a2a387efb43b0c997d5833c789604d168834f6e0d3064bf7bb13d002a6",
        }
        if manifest["repo_id"] == "Qwen/Qwen3-VL-2B-Instruct":
            expected = {
                "model.safetensors": "7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0"
            }
        self.non_thinking = manifest["repo_id"] == "Qwen/Qwen3.5-4B"
        if self.non_thinking:
            if transformers.__version__ != "5.20.1":
                raise ValueError(
                    "Qwen3.5 experiment requires isolated Transformers 5.20.1"
                )
            if not compact:
                raise ValueError("Qwen3.5 requires the bounded compact experiment")
            if (
                grammar_sha256
                != "e860c15add51ef0049b2de546d653b56a92eca71417394c43045467e7f9f9479"
            ):
                raise ValueError(
                    "Qwen3.5 requires the pinned upstream grammar integration"
                )
            expected = {
                "model.safetensors-00001-of-00002.safetensors": "26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61",
                "model.safetensors-00002-of-00002.safetensors": "cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188",
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
                "transformers": transformers.__version__,
                "torch": torch.__version__,
                "enable_thinking": False if self.non_thinking else None,
                "grammar_integration_sha256": grammar_sha256,
                "grammar_upstream_revision": "817f944fcc8851917c40300a47f62d1defc3ffc3"
                if self.non_thinking
                else None,
                "dependency_versions": {
                    package: version(package)
                    for package in (
                        "accelerate",
                        "bitsandbytes",
                        "huggingface-hub",
                        "lm-format-enforcer",
                        "numpy",
                        "Pillow",
                        "safetensors",
                        "tokenizers",
                        "transformers",
                    )
                },
                "quantization": quantization_description,
                "image_max_edge": 848,
                "screening_max_pixels": 131072,
                "verification_max_pixels": 262144,
            }
        }
        self.version = (
            manifest["repo_id"]
            + "@"
            + manifest["revision"]
            + (
                ";nf4-double;bnb=0.48.1;experimental"
                if precision == "nf4"
                else ";bf16;experimental"
            )
        )
        self.runtime_configuration = {
            "image_max_edge": 848,
            "screening_max_pixels": 131072,
            "verification_max_pixels": 262144,
            "quantization": quantization_description,
            "screening_window_sec": 7,
            "screening_overlap_sec": 1,
            "verification_dense_radius_sec": 1,
            "max_images_per_call": 9,
            "max_input_tokens": 4608,
            "screening_mode": "assessments",
        }
        if compact:
            self.runtime_configuration.update(
                {
                    "image_max_edge": 672,
                    "screening_max_pixels": 65536,
                    "verification_max_pixels": 131072,
                    "screening_window_sec": 14,
                    "screening_overlap_sec": 2,
                    "verification_dense_radius_sec": 2,
                    "max_images_per_call": 16,
                    "max_input_tokens": 6144,
                    "screening_mode": "compact explicit assessment",
                    "screening_max_new_tokens": 384,
                    "verification_max_new_tokens": 512,
                    "visual_input": "native video with original PTS"
                    if native_video
                    else "ordered images",
                }
            )
            self.manifest["experimental_recipe"].update(self.runtime_configuration)
            if native_video:
                self.manifest["experimental_recipe"]["native_frames_sha256"] = (
                    hashlib.sha256(
                        Path(__file__).with_name("native_frames.py").read_bytes()
                    ).hexdigest()
                )
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), local_files_only=True, trust_remote_code=False
        )
        self.tokenizer_data = grammar.build_token_enforcer_tokenizer_data(
            self.processor.tokenizer
        )
        quantization = (
            BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                llm_int8_skip_modules=["visual", "lm_head"],
            )
            if precision == "nf4"
            else None
        )
        if self.non_thinking:
            from transformers import Qwen3_5ForConditionalGeneration

            model_class = Qwen3_5ForConditionalGeneration
        else:
            from transformers import Qwen3VLForConditionalGeneration

            model_class = Qwen3VLForConditionalGeneration
        self.model = model_class.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.bfloat16,
            device_map="cuda:0",
            quantization_config=quantization,
            attn_implementation="sdpa",
        ).eval()
        self.generation_token_kwargs = {}
        if self.non_thinking:
            # This checkpoint's nested config says EOS 248044, whereas its
            # actual tokenizer/enforcer uses EOS 248046 (and PAD 248044).
            # With mismatched EOS generation repeatedly emits permitted terminal
            # tokens/whitespace until the token cap after completing valid JSON.
            eos = self.processor.tokenizer.eos_token_id
            pad = self.processor.tokenizer.pad_token_id
            if not isinstance(eos, int) or not isinstance(pad, int):
                raise ValueError("Qwen3.5 requires explicit tokenizer EOS/PAD ids")
            self.generation_token_kwargs = {"eos_token_id": eos, "pad_token_id": pad}
            self.runtime_configuration["effective_generation_token_ids"] = dict(
                self.generation_token_kwargs
            )
            self.manifest["experimental_recipe"]["effective_generation_token_ids"] = (
                dict(self.generation_token_kwargs)
            )

    def infer(self, frames, instruction, deadline, output_schema=None):
        if len(frames) > self.runtime_configuration["max_images_per_call"]:
            raise ProcessingError("RESOURCE_EXHAUSTED", "Image budget exceeded")
        from lmformatenforcer import JsonSchemaParser, CharacterLevelParserConfig
        from lmformatenforcer.integrations.transformers import (
            build_transformers_prefix_allowed_tokens_fn,
        )

        content = []
        images = []
        started = time.perf_counter()
        native = self.native_video and len(frames) > 1
        verify = "Candidate=" in instruction
        telemetry = {
            "frames": len(frames),
            "native_video": native,
            "verification": verify,
        }
        try:
            for frame in frames:
                if not native:
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
                edge = self.runtime_configuration["image_max_edge"]
                image.thumbnail((edge, edge))
                images.append(image)
            if native:
                content.append({"type": "video"})
            content.append({"type": "text", "text": instruction})
            messages = [
                {
                    "role": "system",
                    "content": "Inspect the images as a factual observer. Report only visible actions and temporal context. Do not infer identity, intent, permission, audio, ledger correctness or legal guilt. Return strict JSON.",
                },
                {"role": "user", "content": content},
            ]
            text = self.processor.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                **({"enable_thinking": False} if self.non_thinking else {}),
            )
            pixels = self.runtime_configuration[
                "verification_max_pixels" if verify else "screening_max_pixels"
            ]
            if native:
                from native_frames import native_inputs

                inputs = native_inputs(
                    self.processor, frames, images, text, self.torch, pixels
                )
            else:
                inputs = self.processor(
                    text=[text],
                    images=images,
                    return_tensors="pt",
                    padding=True,
                    images_kwargs={
                        "min_pixels": 1024,
                        "max_pixels": pixels,
                    },
                )
            inputs = inputs.to("cuda:0")
            telemetry["input_tokens"] = int(inputs["input_ids"].shape[-1])
            if (
                telemetry["input_tokens"]
                > self.runtime_configuration["max_input_tokens"]
            ):
                telemetry["input_budget_exceeded"] = True
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
                    max_new_tokens=(512 if verify else 384)
                    if self.compact
                    else (1024 if verify else 768),
                    max_time=remaining,
                    use_cache=True,
                    **self.generation_token_kwargs,
                    **kwargs,
                )
            telemetry["output_tokens"] = int(
                generated.shape[-1] - inputs["input_ids"].shape[-1]
            )
            return self.processor.batch_decode(
                generated[:, inputs["input_ids"].shape[-1] :], skip_special_tokens=True
            )[0]
        finally:
            telemetry["elapsed_sec"] = time.perf_counter() - started
            self.technical_calls.append(telemetry)
            for image in images:
                image.close()
