"""Pinned, owned loopback llama.cpp experiment. No production/cloud fallback."""

import atexit
import base64
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

import httpx
from PIL import Image

from cashproof.errors import ProcessingError


RECEIPT_SHA256 = "10eecab14d30fa89571103c4ad68127ba811c2d338a794a215738869647d3207"
CONVERTED_RECEIPT_SHA256 = (
    "a5f42b2eef703276a0457d9bb81c89e3932190bb741c99c7bba930417467019c"
)
CONVERTED_WEIGHTS = {
    "Qwen3.5-4B-Q8_0.gguf": "34af4c3c962821de6cf93f17422a83c5333a5c2c4dc6377d93ad2c17042e8969",
    "mmproj-Qwen3.5-4B-F16.gguf": "659b59dd44b73b1cd34af6cc424669484b06dc80f4340adf8ea84ad776eef813",
}
WEIGHTS = {
    "Qwen3VL-8B-Instruct-Q4_K_M.gguf": "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2",
    "mmproj-Qwen3VL-8B-Instruct-F16.gguf": "ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38",
}


def checked_file(root, item):
    path = (root / item["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Pinned asset escapes its directory or is absent")
    if path.stat().st_size != item["size"]:
        raise ValueError("Pinned asset size mismatch")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != item["sha256"]:
        raise ValueError("Pinned asset checksum mismatch")


def image_content(frames, pixels, edge):
    """Only locally read, bounded image bytes; source PTS stays in the legend."""
    content = []
    for local_index, frame in enumerate(frames):
        with Image.open(frame["path"]) as source:
            image = source.convert("RGB")
        try:
            scale = min(
                1.0,
                edge / max(image.size),
                math.sqrt(pixels / (image.width * image.height)),
            )
            image.thumbnail(
                (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
            )
            encoded = BytesIO()
            image.save(encoded, format="PNG")
            content.extend(
                [
                    {
                        "type": "text",
                        "text": f"Source index {local_index} at {frame['timestamp_sec']:.6f} source seconds",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(encoded.getvalue()).decode("ascii")
                        },
                    },
                ]
            )
        finally:
            image.close()
    return content


class GGUFModel:
    def __init__(
        self,
        model_dir,
        runtime_dir,
        receipt,
        private_dir,
        screen_pixels=131072,
        cache_prompt=True,
        conversion_receipt=None,
    ):
        self.process = None
        self.client = None
        self.technical_calls = []
        self.native_video = False
        self.compact = True
        self.closed = False
        blob = receipt.read_bytes()
        if hashlib.sha256(blob).hexdigest() != RECEIPT_SHA256:
            raise ValueError("Unexpected provisioning receipt")
        provision = json.loads(blob)
        manifest = json.loads(
            (model_dir / "cashproof-manifest.json").read_text(encoding="utf-8")
        )
        converted = manifest["repo_id"] == "local/Qwen3.5-4B-GGUF"
        expected_weights = WEIGHTS
        if converted:
            if conversion_receipt is None:
                raise ValueError(
                    "Converted checkpoint requires its pinned conversion receipt"
                )
            conversion_blob = conversion_receipt.read_bytes()
            if hashlib.sha256(conversion_blob).hexdigest() != CONVERTED_RECEIPT_SHA256:
                raise ValueError("Unexpected conversion receipt")
            conversion = json.loads(conversion_blob)
            if (
                manifest != conversion["model"]
                or manifest["revision"] != "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
            ):
                raise ValueError("Unexpected converted checkpoint")
            expected_weights = CONVERTED_WEIGHTS
        elif (
            manifest != provision["model"]
            or manifest["revision"] != "f982a07559d4a2f6c8744d840bf6fccab30eea96"
            or conversion_receipt is not None
        ):
            raise ValueError("Unexpected GGUF checkpoint")
        if {
            f["path"]: f["sha256"]
            for f in manifest["files"]
            if f["path"] in expected_weights
        } != expected_weights:
            raise ValueError("Unpinned GGUF weights")
        for item in manifest["files"]:
            checked_file(model_dir, item)
        for item in provision["runtime_files"]:
            checked_file(runtime_dir, item)
        self.runtime_configuration = {
            "image_max_edge": 848,
            "screening_max_pixels": screen_pixels,
            "verification_max_pixels": 262144,
            "screening_window_sec": 14,
            "screening_overlap_sec": 2,
            "verification_dense_radius_sec": 2,
            "max_images_per_call": 16,
            "max_input_tokens": 6144,
            "screening_mode": "local GGUF fact screening",
            "screening_max_new_tokens": 384,
            "verification_max_new_tokens": 1024,
            "visual_input": "ordered images with source PTS",
            "index_mapping": "explicit zero-based local image index; opaque source IDs retained outside visual header",
            "quantization": ("Q8_0" if converted else "Q4_K_M")
            + ", F16 vision projector; q8_0 KV cache",
            "conversion_receipt_sha256": CONVERTED_RECEIPT_SHA256
            if converted
            else None,
            "runtime_release": "llama.cpp b11715 CUDA 12.4",
            "runtime_receipt_sha256": RECEIPT_SHA256,
            "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "image_max_tokens": 256,
            "cache_prompt": cache_prompt,
            "context_shift": False,
            "attention": "llama.cpp CUDA Flash Attention",
            "json_grammar": "llama.cpp b11715 JSON-schema grammar",
        }
        self.manifest = manifest | {
            "experimental_recipe": dict(self.runtime_configuration)
        }
        self.version = (
            manifest["repo_id"]
            + "@"
            + manifest["revision"]
            + ";llama-b11715;experimental"
        )
        private_dir.mkdir(parents=True, exist_ok=True)
        with socket.socket() as bound:
            bound.bind(("127.0.0.1", 0))
            port = bound.getsockname()[1]
        key = secrets.token_urlsafe(32)
        env = os.environ.copy() | {
            "LLAMA_API_KEY": key,
            "HF_HUB_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        }
        command = [
            str((runtime_dir / "llama-server.exe").resolve()),
            "--model",
            str((model_dir / manifest["model_file"]).resolve()),
            "--mmproj",
            str((model_dir / manifest["vision_file"]).resolve()),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--ctx-size",
            "6144",
            "--parallel",
            "1",
            "--gpu-layers",
            "99",
            "--flash-attn",
            "on",
            "--cache-type-k",
            "q8_0",
            "--cache-type-v",
            "q8_0",
            "--batch-size",
            "512",
            "--ubatch-size",
            "256",
            "--image-min-tokens",
            "4",
            "--image-max-tokens",
            "256",
            "--no-context-shift",
            "--no-webui",
            "--log-verbosity",
            "1",
        ]
        with (
            (private_dir / "runtime-stdout.log").open("wb") as stdout,
            (private_dir / "runtime-stderr.log").open("wb") as stderr,
        ):
            self.process = subprocess.Popen(
                command,
                cwd=runtime_dir.resolve(),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        atexit.register(self.close)
        self.client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            headers={"Authorization": "Bearer " + key},
            trust_env=False,
            follow_redirects=False,
        )
        start = time.monotonic()
        try:
            while time.monotonic() - start < 180:
                if self.process.poll() is not None:
                    raise RuntimeError("Owned local GGUF runtime exited during startup")
                try:
                    response = self.client.get("/health", timeout=2)
                    if response.status_code == 200:
                        self.startup_sec = time.monotonic() - start
                        return
                except httpx.TransportError:
                    pass
                time.sleep(0.25)
            raise RuntimeError("Owned local GGUF runtime did not become ready")
        except BaseException:
            self.close()
            raise

    def close(self):
        self.closed = True
        if self.client is not None:
            self.client.close()
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def infer(self, frames, instruction, deadline, output_schema=None):
        if self.closed or self.process.poll() is not None:
            raise ProcessingError(
                "MODEL_UNAVAILABLE", "Owned local runtime unavailable"
            )
        if len(frames) > self.runtime_configuration["max_images_per_call"]:
            raise ProcessingError("RESOURCE_EXHAUSTED", "Image budget exceeded")
        verify = "Candidate=" in instruction
        telemetry = {
            "frames": len(frames),
            "native_video": False,
            "verification": verify,
        }
        start = time.perf_counter()
        try:
            pixels = self.runtime_configuration[
                "verification_max_pixels" if verify else "screening_max_pixels"
            ]
            content = image_content(
                frames, pixels, self.runtime_configuration["image_max_edge"]
            )
            content.append({"type": "text", "text": instruction})
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "Inspect the images as a factual observer. Report only visible actions and temporal context. Do not infer identity, intent, permission, audio, ledger correctness or legal guilt. Return strict JSON.",
                    },
                    {"role": "user", "content": content},
                ],
                "temperature": 0,
                "seed": 0,
                "stream": False,
                "cache_prompt": self.runtime_configuration["cache_prompt"],
                "max_tokens": self.runtime_configuration[
                    "verification_max_new_tokens"
                    if verify
                    else "screening_max_new_tokens"
                ],
                "chat_template_kwargs": {"enable_thinking": False},
            }
            if output_schema:
                payload["response_format"] = {
                    "type": "json_object",
                    "schema": output_schema,
                }
            remaining = deadline - time.time()
            if remaining <= 0:
                raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded")
            try:
                response = self.client.post(
                    "/v1/chat/completions",
                    json=payload,
                    timeout=httpx.Timeout(remaining, connect=min(2, remaining)),
                )
            except httpx.TimeoutException:
                self.close()
                raise ProcessingError(
                    "DEADLINE_EXCEEDED", "Owned local inference timed out"
                ) from None
            if response.status_code != 200:
                # Runtime errors may include prompt content: never surface the body.
                code = (
                    "RESOURCE_EXHAUSTED"
                    if response.status_code in {400, 413, 507}
                    else "PROCESSING_FAILED"
                )
                raise ProcessingError(
                    code, "Owned local runtime rejected bounded request"
                )
            if time.time() > deadline:
                self.close()
                raise ProcessingError(
                    "DEADLINE_EXCEEDED", "Late local inference result discarded"
                )
            if len(response.content) > 256 * 1024:
                raise ProcessingError(
                    "MODEL_OUTPUT_INVALID", "Local response budget exceeded"
                )
            result = response.json()
            usage = result.get("usage", {})
            telemetry.update(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )
            timings = result.get("timings", {})
            telemetry["cached_prompt_tokens"] = timings.get("cache_n", 0)
            choice = result["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ProcessingError(
                    "MODEL_OUTPUT_INVALID", "Local JSON generation did not finish"
                )
            answer = choice["message"].get("content")
            if not isinstance(answer, str):
                raise ProcessingError(
                    "MODEL_OUTPUT_INVALID", "Local runtime returned no JSON string"
                )
            return answer
        finally:
            telemetry["elapsed_sec"] = time.perf_counter() - start
            self.technical_calls.append(telemetry)

    def verify_grammar(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"flag": {"type": "boolean"}},
            "required": ["flag"],
        }
        results = {}
        for flag in (True, False):
            raw = self.infer(
                [],
                "Set flag to " + str(flag).lower() + ". Return only JSON.",
                time.time() + 60,
                schema,
            )
            results[str(flag).lower() + "_permitted"] = json.loads(raw) == {
                "flag": flag
            }
        aggregate = {
            "synthetic_grammar_controls": True,
            "method": "both requested booleans generated under the same schema by the local GGUF runtime",
            **results,
            "passed": all(results.values()),
        }
        (directory / "aggregate.json").write_text(
            json.dumps(aggregate, indent=2), encoding="utf-8"
        )
        print(json.dumps(aggregate), flush=True)
        return aggregate
